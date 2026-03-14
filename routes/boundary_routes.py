"""
routes/boundary_routes.py
--------------------------
Upload farm boundaries in any geospatial format and persist them
to the farms.boundary (PostGIS Polygon) column.

Supported formats:
  - GeoJSON   (.geojson / .json)
  - Shapefile (.zip containing .shp + .dbf + .prj)
  - KML       (.kml)
  - GPX       (.gpx)
  - CSV       (.csv  with a 'geometry' or 'wkt' column in WKT format)

Bulk upload: one file can contain many polygons.
Matching strategy:
  1. Feature property 'farm_id'  → direct ID match
  2. Feature property 'name'     → case-insensitive name match against farms table
  3. No match                    → create a new farm record (name taken from feature)

POST /api/boundaries/upload
GET  /api/boundaries/status
"""

import os, io, json, zipfile, tempfile, traceback
from flask        import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from datetime     import date
from extensions   import db
from core.models  import Farm
from sqlalchemy   import text, func

boundary_bp = Blueprint('boundaries', __name__)

ALLOWED_EXTENSIONS = {'geojson', 'json', 'zip', 'kml', 'gpx', 'csv'}


def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _ext(filename):
    return filename.rsplit('.', 1)[1].lower()


# ── Format parsers ────────────────────────────────────────────

def _parse_geojson(content: bytes):
    """Parse GeoJSON bytes → list of (name, farm_id, wkt_geometry) tuples."""
    import json
    from shapely.geometry import shape
    from shapely import wkt as shapely_wkt

    data = json.loads(content)
    features = data.get('features', []) if data.get('type') == 'FeatureCollection' else [data]
    results = []
    for feat in features:
        try:
            geom = shape(feat['geometry'])
            if geom.geom_type not in ('Polygon', 'MultiPolygon'):
                geom = geom.convex_hull
            props   = feat.get('properties') or {}
            name    = props.get('name') or props.get('Name') or props.get('farm_name') or 'Unknown'
            farm_id = props.get('farm_id') or props.get('id')
            results.append({'name': str(name), 'farm_id': farm_id, 'wkt': geom.wkt})
        except Exception:
            continue
    return results


def _parse_shapefile_zip(zip_bytes: bytes):
    """Unzip shapefile, read with geopandas."""
    import geopandas as gpd
    from shapely import wkt as shapely_wkt

    results = []
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, 'upload.zip')
        with open(zip_path, 'wb') as f:
            f.write(zip_bytes)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(tmpdir)

        # Find .shp file (may be in a sub-folder)
        shp_files = [os.path.join(r, fn)
                     for r, _, files in os.walk(tmpdir)
                     for fn in files if fn.endswith('.shp')]
        if not shp_files:
            raise ValueError('No .shp file found inside the ZIP archive')

        gdf = gpd.read_file(shp_files[0])
        gdf = gdf.to_crs(epsg=4326)  # reproject to WGS84

        for _, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            if geom.geom_type not in ('Polygon', 'MultiPolygon'):
                geom = geom.convex_hull
            name    = row.get('name') or row.get('Name') or row.get('farm_name') or row.get('NAME') or 'Unknown'
            farm_id = row.get('farm_id') or row.get('id') or row.get('ID')
            results.append({'name': str(name), 'farm_id': farm_id, 'wkt': geom.wkt})

    return results


def _parse_kml(content: bytes):
    """Parse KML using stdlib xml.etree — no DLL dependencies."""
    import xml.etree.ElementTree as ET
    from shapely.geometry import Polygon, MultiPolygon
    from shapely.wkt import loads as wkt_loads

    NS = {
        'kml':  'http://www.opengis.net/kml/2.2',
        'kml21':'http://earth.google.com/kml/2.1',
    }

    results = []
    root = ET.fromstring(content)

    # Detect namespace
    tag = root.tag  # e.g. '{http://www.opengis.net/kml/2.2}kml'
    ns  = tag.split('}')[0].lstrip('{') if '}' in tag else ''
    pfx = f'{{{ns}}}' if ns else ''

    def text(el, *tags):
        for t in tags:
            found = el.find(f'.//{pfx}{t}')
            if found is not None and found.text:
                return found.text.strip()
        return None

    def parse_coords(coord_text):
        """'lon,lat,alt lon,lat,alt ...' → list of (lon, lat) tuples."""
        pts = []
        for token in coord_text.strip().split():
            parts = token.split(',')
            if len(parts) >= 2:
                try:
                    pts.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    continue
        return pts

    for placemark in root.iter(f'{pfx}Placemark'):
        try:
            name    = text(placemark, 'name')    or 'Unknown'
            farm_id = text(placemark, 'farm_id') or None

            # Polygon
            outer = placemark.find(f'.//{pfx}outerBoundaryIs//{pfx}coordinates')
            if outer is not None and outer.text:
                pts = parse_coords(outer.text)
                if len(pts) >= 3:
                    geom = Polygon(pts)
                    if geom.is_valid:
                        results.append({'name': name, 'farm_id': farm_id, 'wkt': geom.wkt})
                        continue

            # LineString / track → convex hull
            ls = placemark.find(f'.//{pfx}coordinates')
            if ls is not None and ls.text:
                pts = parse_coords(ls.text)
                if len(pts) >= 3:
                    from shapely.geometry import MultiPoint
                    hull = MultiPoint(pts).convex_hull
                    if hull.geom_type in ('Polygon', 'MultiPolygon'):
                        results.append({'name': name, 'farm_id': farm_id, 'wkt': hull.wkt})
        except Exception:
            continue

    return results


def _parse_gpx(content: bytes):
    """Parse GPX using stdlib xml.etree — no DLL dependencies.
    Extracts tracks and routes, computes convex hull polygon from all points.
    """
    import xml.etree.ElementTree as ET
    from shapely.geometry import MultiPoint

    results = []
    root = ET.fromstring(content)

    tag = root.tag
    ns  = tag.split('}')[0].lstrip('{') if '}' in tag else ''
    pfx = f'{{{ns}}}' if ns else ''

    def get_name(el):
        n = el.find(f'{pfx}name')
        return n.text.strip() if n is not None and n.text else 'GPX_track'

    def collect_points(parent_el, pt_tag):
        pts = []
        for pt in parent_el.iter(f'{pfx}{pt_tag}'):
            try:
                lat = float(pt.get('lat'))
                lon = float(pt.get('lon'))
                pts.append((lon, lat))
            except (TypeError, ValueError):
                continue
        return pts

    # Tracks (trkpt inside trkseg inside trk)
    for trk in root.iter(f'{pfx}trk'):
        pts  = collect_points(trk, 'trkpt')
        name = get_name(trk)
        if len(pts) >= 3:
            hull = MultiPoint(pts).convex_hull
            if hull.geom_type in ('Polygon', 'MultiPolygon'):
                results.append({'name': name, 'farm_id': None, 'wkt': hull.wkt})

    # Routes (rtept inside rte)
    for rte in root.iter(f'{pfx}rte'):
        pts  = collect_points(rte, 'rtept')
        name = get_name(rte)
        if len(pts) >= 3:
            hull = MultiPoint(pts).convex_hull
            if hull.geom_type in ('Polygon', 'MultiPolygon'):
                results.append({'name': name, 'farm_id': None, 'wkt': hull.wkt})

    # Waypoints — treat all wpt in file as one farm boundary
    all_wpts = collect_points(root, 'wpt')
    if len(all_wpts) >= 3:
        hull = MultiPoint(all_wpts).convex_hull
        if hull.geom_type in ('Polygon', 'MultiPolygon'):
            name_el = root.find(f'.//{pfx}name')
            name    = name_el.text.strip() if name_el is not None and name_el.text else 'GPX_waypoints'
            results.append({'name': name, 'farm_id': None, 'wkt': hull.wkt})

    return results


def _parse_csv(content: bytes):
    """Parse CSV with a WKT geometry column (named 'geometry', 'wkt', or 'geom')."""
    import csv
    from shapely import wkt as shapely_wkt

    results = []
    text_content = content.decode('utf-8', errors='replace')
    reader = csv.DictReader(io.StringIO(text_content))

    geom_col = None
    for candidate in ('geometry', 'wkt', 'geom', 'WKT', 'GEOMETRY'):
        if candidate in (reader.fieldnames or []):
            geom_col = candidate
            break

    if not geom_col:
        raise ValueError('CSV must have a geometry/wkt/geom column containing WKT polygon strings')

    for row in reader:
        try:
            geom = shapely_wkt.loads(row[geom_col])
            if geom.geom_type not in ('Polygon', 'MultiPolygon'):
                geom = geom.convex_hull
            name    = row.get('name') or row.get('Name') or row.get('farm_name') or 'Unknown'
            farm_id = row.get('farm_id') or row.get('id')
            results.append({'name': str(name), 'farm_id': farm_id, 'wkt': geom.wkt})
        except Exception:
            continue

    return results


# ── Match & persist ───────────────────────────────────────────

def _match_and_save(parsed_features):
    """
    Match each parsed feature to a DB farm and update its boundary column.
    Returns summary dict.
    """
    updated  = []
    created  = []
    skipped  = []

    for feat in parsed_features:
        wkt     = feat['wkt']
        name    = feat['name']
        farm_id = feat.get('farm_id')

        try:
            farm = None

            # Strategy 1 — direct farm_id match
            if farm_id:
                try:
                    farm = Farm.query.get(int(farm_id))
                except (ValueError, TypeError):
                    pass

            # Strategy 2 — name match (case-insensitive)
            if not farm and name and name != 'Unknown':
                farm = Farm.query.filter(
                    func.lower(Farm.name) == name.strip().lower()
                ).first()

            # Strategy 3 — create new farm
            if not farm:
                # Compute centroid from WKT for lat/lon
                centroid = db.session.scalar(
                    text("SELECT ST_AsText(ST_Centroid(ST_GeomFromText(:wkt, 4326)))"),
                    {'wkt': wkt}
                )
                lat, lon = 0.28, 34.75  # fallback: Kakamega centre
                if centroid:
                    # Parse 'POINT(lon lat)'
                    coords = centroid.replace('POINT(', '').replace(')', '').split()
                    if len(coords) == 2:
                        lon, lat = float(coords[0]), float(coords[1])

                farm = Farm(
                    name=name, crop_type='unknown', status='active',
                    latitude=lat, longitude=lon,
                    planting_date=date.today(),
                )
                db.session.add(farm)
                db.session.flush()  # get farm.id
                created.append({'id': farm.id, 'name': name})

            # Write boundary as PostGIS geometry
            db.session.execute(
                text("""
                     UPDATE farms
                     SET boundary = ST_GeomFromText(:wkt, 4326),
                         location  = ST_Centroid(ST_GeomFromText(:wkt, 4326))
                     WHERE id = :fid
                     """),
                {'wkt': wkt, 'fid': farm.id}
            )

            if farm.id not in [c['id'] for c in created]:
                updated.append({'id': farm.id, 'name': farm.name})

        except Exception as e:
            skipped.append({'name': name, 'reason': str(e)})
            continue

    db.session.commit()
    return {
        'updated': updated,
        'created': created,
        'skipped': skipped,
        'total_processed': len(parsed_features),
    }


# ── Routes ────────────────────────────────────────────────────

@boundary_bp.route('/upload', methods=['POST'])
def upload_boundaries():
    """
    Upload Farm Boundaries (Bulk)
    ---
    tags: [Boundaries]
    consumes:
      - multipart/form-data
    parameters:
      - name: file
        in: formData
        type: file
        required: true
        description: >
          GeoJSON (.geojson), Shapefile ZIP (.zip), KML (.kml),
          GPX (.gpx), or CSV with WKT column (.csv)
    responses:
      200:
        description: Upload result with match/create/skip summary
      400:
        description: Invalid file or format error
    """
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'error': 'Empty filename'}), 400

    filename = secure_filename(file.filename)
    if not _allowed(filename):
        return jsonify({
            'success': False,
            'error': f'Unsupported format. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'
        }), 400

    try:
        content = file.read()
        ext     = _ext(filename)

        if ext in ('geojson', 'json'):
            features = _parse_geojson(content)
        elif ext == 'zip':
            features = _parse_shapefile_zip(content)
        elif ext == 'kml':
            features = _parse_kml(content)
        elif ext == 'gpx':
            features = _parse_gpx(content)
        elif ext == 'csv':
            features = _parse_csv(content)
        else:
            return jsonify({'success': False, 'error': 'Unrecognised format'}), 400

        if not features:
            return jsonify({
                'success': False,
                'error': 'No valid polygon features found in the uploaded file'
            }), 400

        result = _match_and_save(features)

        return jsonify({
            'success':  True,
            'message':  f"Processed {result['total_processed']} features — "
                        f"{len(result['updated'])} updated, "
                        f"{len(result['created'])} created, "
                        f"{len(result['skipped'])} skipped.",
            'summary':  result,
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e), 'trace': traceback.format_exc()}), 500


@boundary_bp.route('/status', methods=['GET'])
def boundary_status():
    """
    Boundary Coverage Summary
    ---
    tags: [Boundaries]
    responses:
      200:
        description: How many farms have polygon boundaries vs point-only
    """
    try:
        total      = Farm.query.filter_by(status='active').count()
        with_poly  = db.session.execute(
            text("SELECT COUNT(*) FROM farms WHERE boundary IS NOT NULL AND status='active'")
        ).scalar()
        return jsonify({
            'success':        True,
            'total_farms':    total,
            'with_boundary':  with_poly,
            'point_only':     total - with_poly,
            'coverage_pct':   round(with_poly / total * 100, 1) if total else 0,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500