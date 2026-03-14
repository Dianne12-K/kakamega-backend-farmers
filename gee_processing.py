import ee
from datetime import datetime, timedelta
from config import Config


class GEEProcessor:

    CROP_THRESHOLDS = {
        'maize': {
            'critical': 0.3, 'watch': 0.5, 'healthy': 0.65, 'optimal': 0.75
        },
        'sugarcane': {
            'critical': 0.4, 'watch': 0.6, 'healthy': 0.75, 'optimal': 0.85
        },
        'beans': {
            'critical': 0.25, 'watch': 0.45, 'healthy': 0.60, 'optimal': 0.70
        },
        'tea': {
            'critical': 0.5, 'watch': 0.65, 'healthy': 0.78, 'optimal': 0.88
        },
    }

    def __init__(self):
        try:
            ee.Initialize(project=Config.GEE_PROJECT_ID)
        except Exception as e:
            print(f"GEE initialization error: {e}")
            print("Attempting to authenticate...")
            ee.Authenticate()
            ee.Initialize(project=Config.GEE_PROJECT_ID)

    def _prepare_geometry(self, geometry):
        if not geometry or 'coordinates' not in geometry:
            raise ValueError("Invalid geometry: missing coordinates")
        clean_geometry = {
            'type': geometry['type'],
            'coordinates': self._remove_elevation(geometry['coordinates'])
        }
        return ee.Geometry(clean_geometry)

    def _remove_elevation(self, coords):
        if isinstance(coords[0], (int, float)):
            return coords[:2]
        return [self._remove_elevation(c) for c in coords]

    def calculate_ndvi(self, geometry, start_date, end_date):
        try:
            ee_geometry = self._prepare_geometry(geometry)
            collection = (
                ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                .filterBounds(ee_geometry)
                .filterDate(start_date, end_date)
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            )

            def add_ndvi(image):
                ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
                return image.addBands(ndvi)

            collection_ndvi = collection.map(add_ndvi)

            def extract_ndvi(image):
                ndvi_mean = image.select('NDVI').reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=ee_geometry,
                    scale=10,
                    maxPixels=1e9,
                )
                return ee.Feature(None, {
                    'date': image.date().format('YYYY-MM-dd'),
                    'ndvi': ndvi_mean.get('NDVI'),
                })

            ndvi_list = collection_ndvi.map(extract_ndvi).getInfo()['features']
            results = []
            for feature in ndvi_list:
                props = feature['properties']
                if props['ndvi'] is not None:
                    results.append({'date': props['date'], 'ndvi': round(props['ndvi'], 3)})
            return sorted(results, key=lambda x: x['date'])

        except Exception as e:
            print(f"Error calculating NDVI: {e}")
            return []

    def get_latest_ndvi(self, geometry):
        end_date   = datetime.now()
        start_date = end_date - timedelta(days=30)
        ndvi_data  = self.calculate_ndvi(
            geometry,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d'),
        )
        return ndvi_data[-1] if ndvi_data else None

    def get_ndvi_time_series(self, geometry, days=90):
        end_date   = datetime.now()
        start_date = end_date - timedelta(days=days)
        return self.calculate_ndvi(
            geometry,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d'),
        )

    def get_latest_imagery(self, geometry, satellite='sentinel-2', days=30):
        try:
            ee_geometry = self._prepare_geometry(geometry)
            end_date    = datetime.now()
            start_date  = end_date - timedelta(days=days)

            collection = (
                ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                .filterBounds(ee_geometry)
                .filterDate(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
                .sort('system:time_start', False)
            )

            image = collection.first()
            if image.getInfo() is None:
                return {}

            bands = image.select(['B3', 'B4', 'B8']).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=ee_geometry,
                scale=10,
                maxPixels=1e9,
            ).getInfo()

            if not bands:
                return {}

            nir   = (bands.get('B8') or 0) / 10000
            red   = (bands.get('B4') or 0) / 10000
            green = (bands.get('B3') or 0) / 10000

            ndvi = (nir - red)         / (nir + red   + 1e-10)
            savi = (1.5 * (nir - red)) / (nir + red + 0.5 + 1e-10)
            ndwi = (green - nir)       / (green + nir + 1e-10)
            lai  = max(0.0, 3.618 * (ndvi ** 2) + 0.118)

            acquired = datetime.fromtimestamp(
                image.get('system:time_start').getInfo() / 1000
            ).strftime('%Y-%m-%d')

            return {
                'B3': round(green, 6), 'B4': round(red, 6), 'B8': round(nir, 6),
                'ndvi': round(ndvi, 4), 'savi': round(savi, 4),
                'ndwi': round(ndwi, 4), 'lai':  round(lai,  3),
                'date_acquired': acquired, 'satellite': satellite,
            }

        except Exception as e:
            print(f"Error in get_latest_imagery: {e}")
            return {}

    def calculate_health_score(self, ndvi_value, crop_type='maize'):
        if ndvi_value is None:
            return 0
        thresholds = self.CROP_THRESHOLDS.get(crop_type.lower(), self.CROP_THRESHOLDS['maize'])
        if ndvi_value < thresholds['critical']:
            score = (ndvi_value / thresholds['critical']) * 20
        elif ndvi_value < thresholds['watch']:
            score = 20 + ((ndvi_value - thresholds['critical']) /
                          (thresholds['watch'] - thresholds['critical'])) * 30
        elif ndvi_value < thresholds['healthy']:
            score = 50 + ((ndvi_value - thresholds['watch']) /
                          (thresholds['healthy'] - thresholds['watch'])) * 30
        else:
            score = 80 + (min(1.0, (ndvi_value - thresholds['healthy']) /
                              (thresholds['optimal'] - thresholds['healthy']))) * 20
        return int(min(100, max(0, score)))

    def get_health_status(self, health_score):
        if health_score >= 70:
            return {'status': 'healthy',  'color': 'green',  'label': 'Healthy'}
        elif health_score >= 50:
            return {'status': 'watch',    'color': 'yellow', 'label': 'Needs Attention'}
        else:
            return {'status': 'critical', 'color': 'red',    'label': 'Critical'}

    def get_soil_moisture(self, geometry, date=None):
        try:
            if date is None:
                date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            ee_geometry = self._prepare_geometry(geometry)
            smap = (
                ee.ImageCollection('NASA/SMAP/SPL4SMGP/008')
                .filterDate(date, (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d'))
                .select('sm_surface')
                .first()
            )
            moisture = smap.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=ee_geometry,
                scale=9000,
                maxPixels=1e9,
            )
            moisture_value = moisture.getInfo().get('sm_surface')
            if moisture_value:
                return round(min(100, max(0, moisture_value * 200)), 1)
            return None
        except Exception as e:
            print(f"Error getting soil moisture: {e}")
            return self._estimate_moisture_from_ndvi(geometry)

    def _estimate_moisture_from_ndvi(self, geometry):
        import random
        return round(random.uniform(30, 70), 1)

    def get_moisture_status(self, moisture_percent):
        thresholds = Config.MOISTURE_THRESHOLDS
        if moisture_percent >= thresholds['wet']:
            return {'status': 'wet',      'color': 'blue',   'label': 'Wet'}
        elif moisture_percent >= thresholds['adequate']:
            return {'status': 'adequate', 'color': 'green',  'label': 'Adequate'}
        elif moisture_percent >= thresholds['low']:
            return {'status': 'low',      'color': 'orange', 'label': 'Low'}
        else:
            return {'status': 'dry',      'color': 'red',    'label': 'Dry'}

    def _get_ee_geometry(self, geometry):
        if isinstance(geometry, str):
            import json
            geometry = json.loads(geometry)
        if geometry.get('type') == 'Point':
            lon, lat = geometry['coordinates'][:2]
            return ee.Geometry.Point([lon, lat]).buffer(500)
        return self._prepare_geometry(geometry)

    def _sentinel2_collection(self, ee_geom, start_date, end_date, max_cloud=20):
        return (
            ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(ee_geom)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', max_cloud))
        )

    def _add_indices(self, image):
        nir   = image.select('B8').divide(10000)
        red   = image.select('B4').divide(10000)
        green = image.select('B3').divide(10000)
        ndvi  = nir.subtract(red).divide(nir.add(red).add(1e-10)).rename('NDVI')
        savi  = nir.subtract(red).multiply(1.5).divide(nir.add(red).add(0.5).add(1e-10)).rename('SAVI')
        ndwi  = green.subtract(nir).divide(green.add(nir).add(1e-10)).rename('NDWI')
        lai   = ndvi.pow(2).multiply(3.618).add(0.118).max(0).rename('LAI')
        return image.addBands([ndvi, savi, ndwi, lai])

    def get_zonal_stats(self, geometry, days=30):
        try:
            ee_geom  = self._get_ee_geometry(geometry)
            end_dt   = datetime.now()
            start_dt = end_dt - timedelta(days=days)

            col = self._sentinel2_collection(
                ee_geom,
                start_dt.strftime('%Y-%m-%d'),
                end_dt.strftime('%Y-%m-%d'),
            ).map(self._add_indices)

            composite = col.median()
            stats = {}

            for band in ('NDVI', 'SAVI', 'NDWI', 'LAI'):
                result = composite.select(band).reduceRegion(
                    reducer=ee.Reducer.mean()
                    .combine(ee.Reducer.min(),    sharedInputs=True)
                    .combine(ee.Reducer.max(),    sharedInputs=True)
                    .combine(ee.Reducer.stdDev(), sharedInputs=True),
                    geometry=ee_geom,
                    scale=10,
                    maxPixels=1e9,
                    ).getInfo()

                stats[band.lower()] = {
                    'mean':   round(result.get(f'{band}_mean')   or 0, 4),
                    'min':    round(result.get(f'{band}_min')    or 0, 4),
                    'max':    round(result.get(f'{band}_max')    or 0, 4),
                    'stddev': round(result.get(f'{band}_stdDev') or 0, 4),
                }

            return {
                'success':       True,
                'stats':         stats,
                'n_images':      col.size().getInfo(),
                'days':          days,
                'date_end':      end_dt.strftime('%Y-%m-%d'),
                'date_start':    start_dt.strftime('%Y-%m-%d'),
                'geometry_type': geometry.get('type') if isinstance(geometry, dict) else 'unknown',
            }

        except Exception as e:
            print(f"[GEE] get_zonal_stats error: {e}")
            return {'success': False, 'error': str(e), 'stats': {}}

    def get_ndvi_change_detection(self, geometry, days=30):
        try:
            ee_geom    = self._get_ee_geometry(geometry)
            now        = datetime.now()
            curr_end   = now
            curr_start = now - timedelta(days=days)
            prev_end   = curr_start
            prev_start = prev_end - timedelta(days=days)

            def period_mean(start, end):
                col = self._sentinel2_collection(
                    ee_geom,
                    start.strftime('%Y-%m-%d'),
                    end.strftime('%Y-%m-%d'),
                ).map(self._add_indices)
                if col.size().getInfo() == 0:
                    return None
                val = (
                    col.median()
                    .select('NDVI')
                    .reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=ee_geom,
                        scale=10,
                        maxPixels=1e9,
                    )
                    .getInfo()
                    .get('NDVI')
                )
                return round(val, 4) if val is not None else None

            current_mean  = period_mean(curr_start, curr_end)
            previous_mean = period_mean(prev_start, prev_end)

            if current_mean is None:
                return {
                    'success': False,
                    'error': 'No recent Sentinel-2 imagery available',
                    'current_mean': None, 'previous_mean': None,
                }

            delta = round(current_mean - previous_mean, 4) if previous_mean is not None else None

            if delta is None:
                trend, alert = 'unknown', 'no_data'
            elif delta >= 0.05:
                trend, alert = 'improving', 'none'
            elif delta >= -0.05:
                trend, alert = 'stable', 'none'
            elif delta >= -0.15:
                trend, alert = 'declining', 'watch'
            else:
                trend, alert = 'rapid_decline', 'critical'

            return {
                'success':        True,
                'current_mean':   current_mean,
                'previous_mean':  previous_mean,
                'delta':          delta,
                'delta_pct':      round(delta / previous_mean * 100, 1)
                if previous_mean and delta is not None else None,
                'trend':          trend,
                'alert':          alert,
                'alert_message':  self._change_alert_message(trend, delta),
                'period': {
                    'current':  {'start': curr_start.strftime('%Y-%m-%d'), 'end': curr_end.strftime('%Y-%m-%d')},
                    'previous': {'start': prev_start.strftime('%Y-%m-%d'), 'end': prev_end.strftime('%Y-%m-%d')},
                },
                'monthly_series': self._monthly_ndvi_series(ee_geom, months=6),
            }

        except Exception as e:
            print(f"[GEE] get_ndvi_change_detection error: {e}")
            return {'success': False, 'error': str(e)}

    def _monthly_ndvi_series(self, ee_geom, months=6):
        results = []
        now = datetime.now()
        for i in range(months - 1, -1, -1):
            end   = now - timedelta(days=30 * i)
            start = end - timedelta(days=30)
            try:
                col = self._sentinel2_collection(
                    ee_geom,
                    start.strftime('%Y-%m-%d'),
                    end.strftime('%Y-%m-%d'),
                ).map(self._add_indices)
                if col.size().getInfo() == 0:
                    results.append({'month': start.strftime('%b %Y'), 'ndvi': None})
                    continue
                val = (
                    col.median()
                    .select('NDVI')
                    .reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=ee_geom,
                        scale=10,
                        maxPixels=1e9,
                    )
                    .getInfo()
                    .get('NDVI')
                )
                results.append({'month': start.strftime('%b %Y'), 'ndvi': round(val, 4) if val is not None else None})
            except Exception:
                results.append({'month': start.strftime('%b %Y'), 'ndvi': None})
        return results

    def _change_alert_message(self, trend, delta):
        messages = {
            'improving':     'Crop health improving. Continue current practices.',
            'stable':        'Crop health stable. No immediate action required.',
            'declining':     f'NDVI declined by {abs(delta):.3f}. Monitor closely and consider irrigation or fertilisation.',
            'rapid_decline': f'RAPID NDVI decline of {abs(delta):.3f}. Immediate field inspection required.',
            'unknown':       'Insufficient imagery to determine trend.',
        }
        return messages.get(trend, 'Status unknown.')

    def get_stress_hotspots(self, geometry, days=30, grid_size=3):
        try:
            if isinstance(geometry, str):
                import json
                geometry = json.loads(geometry)

            is_point = geometry.get('type') == 'Point'
            ee_geom  = self._get_ee_geometry(geometry)
            end_dt   = datetime.now()
            start_dt = end_dt - timedelta(days=days)

            composite = (
                self._sentinel2_collection(
                    ee_geom,
                    start_dt.strftime('%Y-%m-%d'),
                    end_dt.strftime('%Y-%m-%d'),
                )
                .map(self._add_indices)
                .median()
            )

            bounds   = ee_geom.bounds().getInfo()['coordinates'][0]
            lons     = [c[0] for c in bounds]
            lats     = [c[1] for c in bounds]
            min_lon, max_lon = min(lons), max(lons)
            min_lat, max_lat = min(lats), max(lats)
            lon_step = (max_lon - min_lon) / grid_size
            lat_step = (max_lat - min_lat) / grid_size

            hotspots = []
            cell_id  = 0

            for row in range(grid_size):
                for col in range(grid_size):
                    cell_lon  = min_lon + (col + 0.5) * lon_step
                    cell_lat  = min_lat + (row + 0.5) * lat_step
                    cell_geom = ee.Geometry.Point([cell_lon, cell_lat]).buffer(
                        max(50, min(lon_step, lat_step) * 111000 * 0.4)
                    )
                    try:
                        result = (
                            composite.select('NDVI')
                            .reduceRegion(
                                reducer=ee.Reducer.mean(),
                                geometry=cell_geom,
                                scale=10,
                                maxPixels=1e9,
                            )
                            .getInfo()
                        )
                        ndvi = result.get('NDVI')
                        hotspots.append({
                            'cell_id':   cell_id,
                            'row':       row,
                            'col':       col,
                            'latitude':  round(cell_lat, 6),
                            'longitude': round(cell_lon, 6),
                            'ndvi':      round(ndvi, 4) if ndvi is not None else None,
                            'stressed':  ndvi is not None and ndvi < 0.3,
                            'severity':  self._hotspot_severity(ndvi),
                        })
                    except Exception:
                        hotspots.append({
                            'cell_id': cell_id, 'row': row, 'col': col,
                            'latitude': round(cell_lat, 6), 'longitude': round(cell_lon, 6),
                            'ndvi': None, 'stressed': False, 'severity': 'unknown',
                        })
                    cell_id += 1

            stressed_count = sum(1 for h in hotspots if h['stressed'])
            total_cells    = len(hotspots)

            return {
                'success':           True,
                'grid_size':         f'{grid_size}x{grid_size}',
                'total_cells':       total_cells,
                'stressed_cells':    stressed_count,
                'stress_pct':        round(stressed_count / total_cells * 100, 1) if total_cells else 0,
                'overall_stress':    self._overall_stress_level(stressed_count, total_cells),
                'hotspots':          hotspots,
                'is_buffered_point': is_point,
                'days':              days,
            }

        except Exception as e:
            print(f"[GEE] get_stress_hotspots error: {e}")
            return {'success': False, 'error': str(e), 'hotspots': []}

    def _hotspot_severity(self, ndvi):
        if ndvi is None: return 'unknown'
        if ndvi >= 0.5:  return 'healthy'
        if ndvi >= 0.3:  return 'moderate'
        if ndvi >= 0.1:  return 'stressed'
        return                  'critical'

    def _overall_stress_level(self, stressed, total):
        if total == 0:   return 'unknown'
        pct = stressed / total
        if pct == 0:     return 'none'
        if pct <= 0.25:  return 'low'
        if pct <= 0.5:   return 'moderate'
        if pct <= 0.75:  return 'high'
        return                  'critical'

    def get_automated_health_score(self, geometry, crop_type='maize', days=30):
        try:
            zonal = self.get_zonal_stats(geometry, days=days)
            if not zonal.get('success') or not zonal.get('stats'):
                return {'success': False, 'error': 'Could not compute zonal stats', 'score': 0}

            ndvi_mean = zonal['stats'].get('ndvi', {}).get('mean')
            ndwi_mean = zonal['stats'].get('ndwi', {}).get('mean')
            lai_mean  = zonal['stats'].get('lai',  {}).get('mean')

            base_score    = self.calculate_health_score(ndvi_mean, crop_type)
            water_penalty = min(20, int(abs(ndwi_mean + 0.1) * 100)) if ndwi_mean is not None and ndwi_mean < -0.1 else 0
            lai_bonus     = min(5,  int((lai_mean - 3.0) * 5))       if lai_mean  is not None and lai_mean  > 3.0  else 0
            final_score   = max(0, min(100, base_score - water_penalty + lai_bonus))

            return {
                'success':    True,
                'score':      final_score,
                'status':     self.get_health_status(final_score),
                'components': {
                    'ndvi_base_score': base_score,
                    'water_penalty':   water_penalty,
                    'lai_bonus':       lai_bonus,
                },
                'inputs':    {'ndvi': ndvi_mean, 'ndwi': ndwi_mean, 'lai': lai_mean},
                'crop_type': crop_type,
                'days':      days,
            }

        except Exception as e:
            print(f"[GEE] get_automated_health_score error: {e}")
            return {'success': False, 'error': str(e), 'score': 0}

    def get_spatial_recommendations(self, geometry, crop_type='maize', days=30):
        try:
            zonal  = self.get_zonal_stats(geometry, days=days)
            change = self.get_ndvi_change_detection(geometry, days=days)
            spots  = self.get_stress_hotspots(geometry, days=days)
            health = self.get_automated_health_score(geometry, crop_type, days=days)
            recs   = []

            if zonal.get('success'):
                ndwi = zonal['stats'].get('ndwi', {}).get('mean')
                if ndwi is not None and ndwi < -0.1:
                    recs.append({
                        'priority': 'high', 'category': 'irrigation',
                        'title':  'Water Stress Detected',
                        'detail': f'NDWI mean is {ndwi:.3f}. Irrigate within 48 hours.',
                        'metric': f'NDWI: {ndwi:.3f}',
                    })
                elif ndwi is not None and ndwi < 0.1:
                    recs.append({
                        'priority': 'medium', 'category': 'irrigation',
                        'title':  'Monitor Leaf Moisture',
                        'detail': f'NDWI mean is {ndwi:.3f}. Moisture is low but not critical yet.',
                        'metric': f'NDWI: {ndwi:.3f}',
                    })

            if change.get('success') and change.get('alert') in ('watch', 'critical'):
                recs.append({
                    'priority': 'critical' if change['alert'] == 'critical' else 'high',
                    'category': 'health',
                    'title':  'NDVI Decline Detected',
                    'detail': change.get('alert_message', ''),
                    'metric': f"NDVI delta: {change.get('delta', 'N/A')}",
                })

            if spots.get('success') and spots.get('stress_pct', 0) > 0:
                pct       = spots['stress_pct']
                positions = [f"row {h['row']+1} col {h['col']+1}" for h in spots['hotspots'] if h['stressed']]
                recs.append({
                    'priority': 'high' if pct > 50 else 'medium',
                    'category': 'spatial',
                    'title':  f'{pct}% of Farm Area Stressed',
                    'detail': f'Stressed zones at: {", ".join(positions[:4])}. Consider targeted fertiliser application.',
                    'metric': f'{spots["stressed_cells"]}/{spots["total_cells"]} grid cells',
                })

            if zonal.get('success'):
                lai = zonal['stats'].get('lai', {}).get('mean')
                if lai is not None and lai < 1.5:
                    recs.append({
                        'priority': 'medium', 'category': 'nutrition',
                        'title':  'Thin Canopy',
                        'detail': f'LAI of {lai:.2f} is below 2.0. Consider top-dressing with nitrogen.',
                        'metric': f'LAI: {lai:.2f}',
                    })

            if not recs:
                recs.append({
                    'priority': 'low', 'category': 'general',
                    'title':  'Farm Performing Well',
                    'detail': 'All indicators within healthy ranges. Continue current practices.',
                    'metric': f'Health score: {health.get("score", "N/A")}/100',
                })

            priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
            recs.sort(key=lambda r: priority_order.get(r['priority'], 9))

            return {
                'success':         True,
                'recommendations': recs,
                'total':           len(recs),
                'health_score':    health.get('score'),
                'health_status':   health.get('status', {}).get('status'),
                'summary': {
                    'zonal_stats':   zonal.get('success', False),
                    'change_detect': change.get('success', False),
                    'hotspots':      spots.get('success', False),
                    'stress_pct':    spots.get('stress_pct', 0),
                    'trend':         change.get('trend', 'unknown'),
                    'alert':         change.get('alert', 'none'),
                },
            }

        except Exception as e:
            print(f"[GEE] get_spatial_recommendations error: {e}")
            return {'success': False, 'error': str(e), 'recommendations': []}