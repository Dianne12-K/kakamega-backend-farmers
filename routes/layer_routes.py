"""
routes/layer_routes.py
Upload boundary files as named map layers.
Each file becomes a layer; each polygon in the file becomes a farm in that layer.
All original feature properties are preserved in farms.attributes (JSONB).
"""
import copy, os, io, json, zipfile, tempfile, traceback
from flask          import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from datetime       import date
from extensions     import db
from core.models    import Farm, MapLayer
from sqlalchemy     import text, func

layer_bp = Blueprint('layers', __name__)

ALLOWED = {'geojson', 'json', 'zip', 'kml', 'gpx', 'csv'}


def _ext(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''


# ── Helpers ────────────────────────────────────────────────────────────────────

def _clean_props(props: dict) -> dict:
    """
    Return a JSON-safe copy of props with geometry columns stripped out.
    Coerces any non-serialisable value to str so nothing is silently lost.
    """
    GEOM_KEYS = {'geometry', 'geom', 'wkt', 'the_geom', 'shape', 'GEOMETRY', 'GEOM'}
    out = {}
    for k, v in props.items():
        if k in GEOM_KEYS:
            continue
        try:
            json.dumps(v)
            out[k] = v
        except (TypeError, ValueError):
            out[k] = str(v)
    return out


# ── Parsers ────────────────────────────────────────────────────────────────────

def _parse_geojson(content):
    from shapely.geometry import shape
    data = json.loads(content)
    features = data.get('features', []) if data.get('type') == 'FeatureCollection' else [data]
    results = []
    for feat in features:
        try:
            geom  = shape(feat['geometry'])
            if geom.geom_type not in ('Polygon', 'MultiPolygon'):
                geom = geom.convex_hull
            props = feat.get('properties') or {}
            results.append({
                'name':  props.get('name') or props.get('Name') or props.get('farm_name') or 'Unnamed Parcel',
                'wkt':   geom.wkt,
                'props': props,          # ← full original props kept
            })
        except Exception:
            continue
    return results


def _parse_shapefile_zip(zip_bytes):
    import geopandas as gpd
    results = []
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, 'upload.zip')
        open(zip_path, 'wb').write(zip_bytes)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmpdir)
        shps = [os.path.join(r, f) for r, _, fs in os.walk(tmpdir) for f in fs if f.endswith('.shp')]
        if not shps:
            raise ValueError('No .shp file found inside ZIP')
        gdf = gpd.read_file(shps[0]).to_crs(epsg=4326)
        for _, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            if geom.geom_type not in ('Polygon', 'MultiPolygon'):
                geom = geom.convex_hull
            props = row.to_dict()
            name  = (props.get('name') or props.get('Name') or props.get('NAME')
                     or props.get('farm_name') or 'Unnamed Parcel')
            results.append({'name': str(name), 'wkt': geom.wkt, 'props': props})
    return results


def _parse_kml(content):
    import xml.etree.ElementTree as ET
    from shapely.geometry import Polygon, MultiPoint
    results = []
    root = ET.fromstring(content)
    ns   = root.tag.split('}')[0].lstrip('{') if '}' in root.tag else ''
    p    = f'{{{ns}}}' if ns else ''

    def coords(text):
        pts = []
        for tok in text.strip().split():
            parts = tok.split(',')
            if len(parts) >= 2:
                try:
                    pts.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    pass
        return pts

    def extended_data(pm):
        """Extract KML ExtendedData/SimpleData into a dict."""
        ed = pm.find(f'.//{p}ExtendedData')
        out = {}
        if ed is None:
            return out
        for sd in ed.iter(f'{p}SimpleData'):
            key = sd.get('name', '')
            out[key] = sd.text or ''
        return out

    for pm in root.iter(f'{p}Placemark'):
        try:
            name_el = pm.find(f'{p}name')
            name    = name_el.text.strip() if name_el is not None and name_el.text else 'Unnamed Parcel'
            props   = {'name': name, **extended_data(pm)}

            outer = pm.find(f'.//{p}outerBoundaryIs//{p}coordinates')
            if outer is not None and outer.text:
                pts = coords(outer.text)
                if len(pts) >= 3:
                    results.append({'name': name, 'wkt': Polygon(pts).wkt, 'props': props})
                    continue
            ls = pm.find(f'.//{p}coordinates')
            if ls is not None and ls.text:
                pts = coords(ls.text)
                if len(pts) >= 3:
                    hull = MultiPoint(pts).convex_hull
                    if hull.geom_type in ('Polygon', 'MultiPolygon'):
                        results.append({'name': name, 'wkt': hull.wkt, 'props': props})
        except Exception:
            continue
    return results


def _parse_gpx(content):
    import xml.etree.ElementTree as ET
    from shapely.geometry import MultiPoint
    results = []
    root = ET.fromstring(content)
    ns   = root.tag.split('}')[0].lstrip('{') if '}' in root.tag else ''
    p    = f'{{{ns}}}' if ns else ''

    def get_name(el):
        n = el.find(f'{p}name')
        return n.text.strip() if n is not None and n.text else 'GPX Track'

    def collect(parent, tag):
        pts = []
        for pt in parent.iter(f'{p}{tag}'):
            try:
                pts.append((float(pt.get('lon')), float(pt.get('lat'))))
            except (TypeError, ValueError):
                pass
        return pts

    for trk in root.iter(f'{p}trk'):
        pts = collect(trk, 'trkpt')
        if len(pts) >= 3:
            hull = MultiPoint(pts).convex_hull
            if hull.geom_type in ('Polygon', 'MultiPolygon'):
                name = get_name(trk)
                results.append({'name': name, 'wkt': hull.wkt, 'props': {'name': name}})

    for rte in root.iter(f'{p}rte'):
        pts = collect(rte, 'rtept')
        if len(pts) >= 3:
            hull = MultiPoint(pts).convex_hull
            if hull.geom_type in ('Polygon', 'MultiPolygon'):
                name = get_name(rte)
                results.append({'name': name, 'wkt': hull.wkt, 'props': {'name': name}})

    return results


def _parse_csv(content):
    import csv
    from shapely import wkt as swkt
    results = []
    reader  = csv.DictReader(io.StringIO(content.decode('utf-8', errors='replace')))
    geom_col = next((c for c in (reader.fieldnames or [])
                     if c.lower() in ('geometry', 'wkt', 'geom')), None)
    if not geom_col:
        raise ValueError('CSV must have a geometry/wkt/geom column')
    for row in reader:
        try:
            geom = swkt.loads(row[geom_col])
            if geom.geom_type not in ('Polygon', 'MultiPolygon'):
                geom = geom.convex_hull
            props = dict(row)
            name  = props.get('name') or props.get('Name') or props.get('farm_name') or 'Unnamed Parcel'
            results.append({'name': str(name), 'wkt': geom.wkt, 'props': props})
        except Exception:
            continue
    return results


def _dispatch_parser(filename, content):
    ext = _ext(filename)
    if ext in ('geojson', 'json'): return _parse_geojson(content)
    if ext == 'zip':               return _parse_shapefile_zip(content)
    if ext == 'kml':               return _parse_kml(content)
    if ext == 'gpx':               return _parse_gpx(content)
    if ext == 'csv':               return _parse_csv(content)
    raise ValueError(f'Unsupported format: {ext}')


# ── Save farms (preserving all original attributes) ────────────────────────────

def _save_farms(features, layer_id):
    saved, skipped = [], []
    for feat in features:
        sp = db.session.begin_nested()
        try:
            wkt        = feat['wkt']
            name       = feat['name']
            props      = feat.get('props') or {}
            crop_type  = props.get('crop_type') or props.get('crop') or 'unknown'

            # Strip geometry blobs, coerce non-JSON values → keep everything else
            attributes = _clean_props(props)

            row = db.session.execute(
                text("""
                    SELECT
                        ST_X(ST_Centroid(ST_GeomFromText(:wkt, 4326)))        AS lon,
                        ST_Y(ST_Centroid(ST_GeomFromText(:wkt, 4326)))        AS lat,
                        ST_Area(ST_GeomFromText(:wkt, 4326)::geography)/10000 AS area_ha,
                        ST_IsValid(ST_GeomFromText(:wkt, 4326))               AS valid
                """),
                {'wkt': wkt}
            ).fetchone()

            if not row.valid:
                raise ValueError(f'Invalid geometry for "{name}"')

            result = db.session.execute(
                text("""
                     INSERT INTO farms
                     (name, crop_type, status, latitude, longitude,
                      area_ha, layer_id, planting_date, boundary, location, attributes)
                     VALUES
                         (:name, :crop_type, 'active', :lat, :lon,
                          :area_ha, :layer_id, :today,
                          ST_GeomFromText(:wkt, 4326),
                          ST_Centroid(ST_GeomFromText(:wkt, 4326)),
                          :attributes::jsonb)
                         RETURNING id
                     """),
                {
                    'name':       name,
                    'crop_type':  crop_type,
                    'lat':        row.lat,
                    'lon':        row.lon,
                    'area_ha':    round(float(row.area_ha), 4) if row.area_ha else None,
                    'layer_id':   layer_id,
                    'today':      date.today().isoformat(),
                    'wkt':        wkt,
                    'attributes': json.dumps(attributes),
                }
            )
            farm_id = result.fetchone()[0]
            sp.commit()
            saved.append({'id': farm_id, 'name': name})
        except Exception as e:
            sp.rollback()
            skipped.append({'name': feat.get('name', '?'), 'reason': str(e)})
    return saved, skipped


# ── GET /api/layers ────────────────────────────────────────────────────────────

@layer_bp.route('/', methods=['GET'])
def list_layers():
    """
    List All Map Layers
    ---
    tags: [Layers]
    responses:
      200: {description: All layers with farm counts and UUIDs}
    """
    try:
        layers = MapLayer.query.order_by(MapLayer.created_at.desc()).all()
        return jsonify({'success': True, 'layers': [l.to_dict() for l in layers]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── POST /api/layers/upload ────────────────────────────────────────────────────

@layer_bp.route('/upload', methods=['POST'])
def upload_layer():
    """
    Upload a Boundary File as a Named Layer
    ---
    tags: [Layers]
    consumes: [multipart/form-data]
    parameters:
      - {name: file,        in: formData, type: file,   required: true}
      - {name: name,        in: formData, type: string, required: true}
      - {name: color,       in: formData, type: string, required: false}
      - {name: description, in: formData, type: string, required: false}
    responses:
      200: {description: Layer created with farm count}
      400: {description: Validation error}
    """
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    file        = request.files['file']
    layer_name  = (request.form.get('name') or '').strip()
    color       = (request.form.get('color') or '#3b82f6').strip()
    description = (request.form.get('description') or '').strip()

    if not layer_name:
        return jsonify({'success': False, 'error': 'Layer name is required'}), 400
    if not file.filename:
        return jsonify({'success': False, 'error': 'Empty filename'}), 400

    filename = secure_filename(file.filename)
    if _ext(filename) not in ALLOWED:
        return jsonify({'success': False,
                        'error': f'Unsupported format. Allowed: {", ".join(ALLOWED)}'}), 400

    try:
        content  = file.read()
        features = _dispatch_parser(filename, content)

        if not features:
            return jsonify({'success': False,
                            'error': 'No valid polygon features found in the file'}), 400

        layer = MapLayer(name=layer_name, color=color, description=description or None)
        db.session.add(layer)
        db.session.flush()

        saved, skipped = _save_farms(features, layer.id)

        db.session.commit()

        return jsonify({
            'success': True,
            'layer':   layer.to_dict(),
            'message': f'{len(saved)} parcels added to layer "{layer_name}".',
            'saved':   saved,
            'skipped': skipped,
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e), 'trace': traceback.format_exc()}), 500


# ── PATCH /api/layers/<id> ─────────────────────────────────────────────────────

@layer_bp.route('/<int:layer_id>', methods=['PATCH'])
def update_layer(layer_id):
    """
    Update Layer Name, Color, Visibility or Description
    ---
    tags: [Layers]
    """
    try:
        layer = MapLayer.query.get(layer_id)
        if not layer:
            return jsonify({'success': False, 'error': 'Layer not found'}), 404
        data = request.get_json() or {}
        if 'name'        in data: layer.name        = data['name']
        if 'color'       in data: layer.color       = data['color']
        if 'visible'     in data: layer.visible     = bool(data['visible'])
        if 'description' in data: layer.description = data['description']
        db.session.commit()
        return jsonify({'success': True, 'layer': layer.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── DELETE /api/layers/<id> ────────────────────────────────────────────────────

@layer_bp.route('/<int:layer_id>', methods=['DELETE'])
def delete_layer(layer_id):
    """
    Delete a Layer and All Its Farms
    ---
    tags: [Layers]
    """
    try:
        layer = MapLayer.query.get(layer_id)
        if not layer:
            return jsonify({'success': False, 'error': 'Layer not found'}), 404
        farm_count = layer.farms.count()
        Farm.query.filter_by(layer_id=layer_id).delete()
        db.session.delete(layer)
        db.session.commit()
        return jsonify({'success': True,
                        'message': f'Layer "{layer.name}" and {farm_count} farms deleted.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/layers/<id>/geojson ───────────────────────────────────────────────

@layer_bp.route('/<int:layer_id>/geojson', methods=['GET'])
def layer_geojson(layer_id):
    """
    Get Layer as GeoJSON FeatureCollection.
    Each feature's properties include the original file attributes
    under the 'attributes' key, plus system fields at the top level.
    ---
    tags: [Layers]
    """
    try:
        layer = MapLayer.query.get(layer_id)
        if not layer:
            return jsonify({'success': False, 'error': 'Layer not found'}), 404

        farms    = Farm.query.filter_by(layer_id=layer_id, status='active').all()
        features = []
        for farm in farms:
            if not farm.boundary:
                continue
            geom_json = db.session.scalar(func.ST_AsGeoJSON(farm.boundary))
            if not geom_json:
                continue

            # Merge original attributes + system fields into one flat properties dict.
            # Original file attributes come first so system fields always win on collision.
            original = farm.attributes or {}
            props = {
                **original,                          # ← all original parcel attributes
                # System / computed fields (overwrite any same-named original key)
                'id':           farm.id,
                'name':         farm.name,
                'crop_type':    farm.crop_type,
                'area_ha':      float(farm.area_ha) if farm.area_ha else None,
                'status':       farm.status,
                'layer_id':     farm.layer_id,
                'layer_uuid':   str(layer.uuid) if layer.uuid else None,
                'layer_name':   layer.name,
                'layer_color':  layer.color,
            }

            features.append({
                'type':       'Feature',
                'geometry':   json.loads(geom_json),
                'properties': props,
            })

        return jsonify({
            'type':        'FeatureCollection',
            'layer_id':    layer_id,
            'layer_uuid':  str(layer.uuid) if layer.uuid else None,
            'layer_name':  layer.name,
            'layer_color': layer.color,
            'count':       len(features),
            'features':    features,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/layers/<id>/attributes ───────────────────────────────────────────
# Returns the distinct attribute keys found across all parcels in a layer.
# Useful for the frontend to know what columns are available.

@layer_bp.route('/<int:layer_id>/attributes', methods=['GET'])
def layer_attribute_schema(layer_id):
    """
    Get the attribute schema (distinct keys) for a layer's parcels.
    ---
    tags: [Layers]
    responses:
      200: {description: List of attribute key names found in this layer}
    """
    try:
        layer = MapLayer.query.get(layer_id)
        if not layer:
            return jsonify({'success': False, 'error': 'Layer not found'}), 404

        # Sample up to 200 farms to discover keys (fast, avoids full table scan)
        rows = db.session.execute(
            text("""
                 SELECT DISTINCT jsonb_object_keys(attributes) AS key
                 FROM   farms
                 WHERE  layer_id = :lid
                   AND  attributes IS NOT NULL
                   AND  attributes != '{}'::jsonb
                     LIMIT  200
                 """),
            {'lid': layer_id}
        ).fetchall()

        keys = sorted({r.key for r in rows})
        return jsonify({
            'success':   True,
            'layer_id':  layer_id,
            'layer_uuid': str(layer.uuid) if layer.uuid else None,
            'keys':      keys,
            'count':     len(keys),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/layers/<id>/debug ─────────────────────────────────────────────────

@layer_bp.route('/<int:layer_id>/debug', methods=['GET'])
def layer_debug(layer_id):
    """Quick check: how many farms exist for this layer, how many have boundaries."""
    try:
        total = Farm.query.filter_by(layer_id=layer_id).count()
        rows  = db.session.execute(
            text("SELECT id, name, boundary IS NOT NULL AS has_boundary FROM farms WHERE layer_id=:lid"),
            {'lid': layer_id}
        ).fetchall()
        return jsonify({
            'layer_id':    layer_id,
            'total_farms': total,
            'farms': [{'id': r.id, 'name': r.name, 'has_boundary': r.has_boundary} for r in rows],
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500