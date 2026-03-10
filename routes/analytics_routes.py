"""
routes/analytics_routes.py
---------------------------
Analytics & dashboard endpoints.
Powers charts, summaries and stats on the Vue.js frontend.
"""
from flask import Blueprint, request, jsonify
from extensions import db
from core.models import Farm, NDVIReading, MoistureReading, MarketPrice, Subcounty, Ward
from sqlalchemy import func, text, distinct
from datetime import date, timedelta

analytics_bp = Blueprint('analytics', __name__)


# ── GET /api/analytics/farms/summary ─────────────────────────────────────────

@analytics_bp.route('/farms/summary', methods=['GET'])
def farms_summary():
    """
    Farm Portfolio Summary
    ---
    tags:
      - Analytics
    description: Total farms, area breakdown, crop distribution and status counts.
    responses:
      200:
        description: Farm summary statistics
    """
    try:
        total_farms  = Farm.query.filter_by(status='active').count()
        total_area   = db.session.query(func.sum(Farm.area_ha)).filter_by(status='active').scalar() or 0

        # Crop type breakdown
        crop_counts = db.session.query(
            Farm.crop_type,
            func.count(Farm.id).label('count'),
            func.sum(Farm.area_ha).label('total_area_ha')
        ).filter_by(status='active').group_by(Farm.crop_type).all()

        # Status breakdown
        status_counts = db.session.query(
            Farm.status,
            func.count(Farm.id).label('count')
        ).group_by(Farm.status).all()

        # Farms per ward
        farms_per_ward = db.session.query(
            Ward.name,
            func.count(Farm.id).label('farm_count')
        ).join(Farm, Farm.ward_id == Ward.id).group_by(Ward.name).order_by(func.count(Farm.id).desc()).limit(10).all()

        return jsonify({
            'success':     True,
            'summary': {
                'total_farms':   total_farms,
                'total_area_ha': round(float(total_area), 2),
                'avg_farm_size': round(float(total_area) / total_farms, 2) if total_farms else 0,
            },
            'by_crop': [
                {
                    'crop_type':    r.crop_type or 'Unknown',
                    'count':        r.count,
                    'total_area_ha': round(float(r.total_area_ha or 0), 2),
                    'percent':      round(r.count / total_farms * 100, 1) if total_farms else 0,
                }
                for r in crop_counts
            ],
            'by_status': [
                {'status': r.status, 'count': r.count}
                for r in status_counts
            ],
            'top_wards': [
                {'ward': r.name, 'farm_count': r.farm_count}
                for r in farms_per_ward
            ],
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/analytics/farms/health-overview ─────────────────────────────────

@analytics_bp.route('/farms/health-overview', methods=['GET'])
def farms_health_overview():
    """
    Farm Health Overview — % Healthy vs At-Risk
    ---
    tags:
      - Analytics
    description: >
      Uses the latest NDVI reading per farm to categorize farms as
      Healthy, Watch, or Critical. Powers the dashboard health chart.
    responses:
      200:
        description: Health distribution across all active farms
    """
    try:
        # Latest NDVI per farm using a subquery
        latest_ndvi_subq = db.session.query(
            NDVIReading.farm_id,
            func.max(NDVIReading.date).label('latest_date')
        ).group_by(NDVIReading.farm_id).subquery()

        latest_readings = db.session.query(NDVIReading).join(
            latest_ndvi_subq,
            (NDVIReading.farm_id == latest_ndvi_subq.c.farm_id) &
            (NDVIReading.date == latest_ndvi_subq.c.latest_date)
        ).all()

        # Categorize
        healthy  = [r for r in latest_readings if r.health_score and r.health_score >= 70]
        watch    = [r for r in latest_readings if r.health_score and 40 <= r.health_score < 70]
        critical = [r for r in latest_readings if r.health_score and r.health_score < 40]
        no_data  = Farm.query.filter_by(status='active').count() - len(latest_readings)

        total_with_data = len(latest_readings)

        return jsonify({
            'success': True,
            'health_overview': {
                'healthy': {
                    'count':   len(healthy),
                    'percent': round(len(healthy) / total_with_data * 100, 1) if total_with_data else 0,
                    'label':   'Healthy (score ≥ 70)',
                    'color':   '#27AE60',
                },
                'watch': {
                    'count':   len(watch),
                    'percent': round(len(watch) / total_with_data * 100, 1) if total_with_data else 0,
                    'label':   'Watch (score 40–69)',
                    'color':   '#F39C12',
                },
                'critical': {
                    'count':   len(critical),
                    'percent': round(len(critical) / total_with_data * 100, 1) if total_with_data else 0,
                    'label':   'Critical (score < 40)',
                    'color':   '#E74C3C',
                },
                'no_data': {
                    'count':   no_data,
                    'label':   'No satellite data yet',
                    'color':   '#BDC3C7',
                },
            },
            'farms_with_data': total_with_data,
            'critical_farms': [
                {
                    'farm_id':     r.farm_id,
                    'health_score': r.health_score,
                    'ndvi':        float(r.ndvi_value) if r.ndvi_value else None,
                    'date':        str(r.date),
                }
                for r in critical
            ],
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/analytics/markets/price-trends/<crop> ───────────────────────────

@analytics_bp.route('/markets/price-trends/<crop_type>', methods=['GET'])
def price_trends(crop_type):
    """
    Market Price Trends for a Crop Over Time
    ---
    tags:
      - Analytics
    parameters:
      - name: crop_type
        in: path
        type: string
        required: true
        description: e.g. maize, beans, sugarcane
      - name: days
        in: query
        type: integer
        default: 90
    responses:
      200:
        description: Price history with min, max, avg trend line
    """
    try:
        days  = int(request.args.get('days', 90))
        since = date.today() - timedelta(days=days)

        prices = db.session.query(
            MarketPrice.date_recorded,
            func.avg(MarketPrice.price).label('avg_price'),
            func.min(MarketPrice.price).label('min_price'),
            func.max(MarketPrice.price).label('max_price'),
            func.count(MarketPrice.id).label('num_markets'),
        ).filter(
            MarketPrice.crop_type == crop_type.lower(),
            MarketPrice.date_recorded >= since
        ).group_by(MarketPrice.date_recorded).order_by(MarketPrice.date_recorded.asc()).all()

        trend = [
            {
                'date':        str(r.date_recorded),
                'avg_price':   round(float(r.avg_price), 2),
                'min_price':   round(float(r.min_price), 2),
                'max_price':   round(float(r.max_price), 2),
                'num_markets': r.num_markets,
            }
            for r in prices
        ]

        # Overall stats
        all_prices = db.session.query(MarketPrice).filter(
            MarketPrice.crop_type == crop_type.lower(),
            MarketPrice.is_current == True
        ).all()

        current_avg = sum(float(p.price) for p in all_prices) / len(all_prices) if all_prices else 0
        current_min = min(float(p.price) for p in all_prices) if all_prices else 0
        current_max = max(float(p.price) for p in all_prices) if all_prices else 0

        return jsonify({
            'success':   True,
            'crop_type': crop_type,
            'days':      days,
            'trend':     trend,
            'current': {
                'avg_price': round(current_avg, 2),
                'min_price': round(current_min, 2),
                'max_price': round(current_max, 2),
                'unit':      all_prices[0].unit if all_prices else 'per 90kg bag',
                'num_markets': len(all_prices),
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/analytics/subcounty/<id>/stats ──────────────────────────────────

@analytics_bp.route('/subcounty/<int:subcounty_id>/stats', methods=['GET'])
def subcounty_stats(subcounty_id):
    """
    Per-Subcounty Dashboard Statistics
    ---
    tags:
      - Analytics
    parameters:
      - name: subcounty_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Full stats for a subcounty — farms, health, yield, wards
      404:
        description: Subcounty not found
    """
    try:
        subcounty = Subcounty.query.get(subcounty_id)
        if not subcounty:
            return jsonify({'success': False, 'error': 'Subcounty not found'}), 404

        # All wards in subcounty
        wards = Ward.query.filter_by(subcounty_id=subcounty_id).all()
        ward_ids = [w.id for w in wards]

        # Farms in this subcounty (via ward)
        farms = Farm.query.filter(Farm.ward_id.in_(ward_ids), Farm.status == 'active').all()
        farm_ids = [f.id for f in farms]

        total_farms = len(farms)
        total_area  = sum(float(f.area_ha or 0) for f in farms)

        # Crop breakdown
        crop_counts = {}
        for f in farms:
            crop = f.crop_type or 'Unknown'
            crop_counts[crop] = crop_counts.get(crop, 0) + 1

        # Latest health scores
        health_scores = []
        if farm_ids:
            latest_subq = db.session.query(
                NDVIReading.farm_id,
                func.max(NDVIReading.date).label('latest_date')
            ).filter(NDVIReading.farm_id.in_(farm_ids)).group_by(NDVIReading.farm_id).subquery()

            readings = db.session.query(NDVIReading).join(
                latest_subq,
                (NDVIReading.farm_id == latest_subq.c.farm_id) &
                (NDVIReading.date == latest_subq.c.latest_date)
            ).all()
            health_scores = [r.health_score for r in readings if r.health_score]

        avg_health = round(sum(health_scores) / len(health_scores), 1) if health_scores else None

        # Yield estimates
        yields = [float(f.yield_estimate_tons) for f in farms if f.yield_estimate_tons]
        total_yield = round(sum(yields), 2)
        avg_yield   = round(sum(yields) / len(yields), 2) if yields else None

        return jsonify({
            'success':      True,
            'subcounty':    subcounty.name,
            'subcounty_id': subcounty_id,
            'summary': {
                'total_wards':       len(wards),
                'total_farms':       total_farms,
                'total_area_ha':     round(total_area, 2),
                'avg_farm_size_ha':  round(total_area / total_farms, 2) if total_farms else 0,
                'total_yield_tons':  total_yield,
                'avg_yield_tons':    avg_yield,
                'avg_health_score':  avg_health,
            },
            'by_crop':  [{'crop_type': k, 'count': v} for k, v in sorted(crop_counts.items(), key=lambda x: -x[1])],
            'wards': [
                {
                    'id':         w.id,
                    'name':       w.name,
                    'population': w.population,
                    'area_sq_km': float(w.area_sq_km) if w.area_sq_km else None,
                    'farm_count': Farm.query.filter_by(ward_id=w.id, status='active').count(),
                }
                for w in wards
            ],
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/analytics/platform/overview ─────────────────────────────────────

@analytics_bp.route('/platform/overview', methods=['GET'])
def platform_overview():
    """
    Platform-Wide Overview — Top-Level Dashboard Numbers
    ---
    tags:
      - Analytics
    description: The single endpoint that powers the main dashboard KPI cards.
    responses:
      200:
        description: Platform-wide key statistics
    """
    try:
        total_farms       = Farm.query.filter_by(status='active').count()
        total_area        = db.session.query(func.sum(Farm.area_ha)).filter_by(status='active').scalar() or 0
        total_subcounties = Subcounty.query.count()
        total_wards       = Ward.query.count()

        # Farms with recent satellite data (last 30 days)
        since_30 = date.today() - timedelta(days=30)
        farms_monitored = db.session.query(
            func.count(distinct(NDVIReading.farm_id))
        ).filter(NDVIReading.date >= since_30).scalar() or 0

        # Average health score
        avg_health = db.session.query(func.avg(NDVIReading.health_score)).scalar()

        # Most common crop
        top_crop = db.session.query(
            Farm.crop_type, func.count(Farm.id).label('cnt')
        ).filter_by(status='active').group_by(Farm.crop_type).order_by(func.count(Farm.id).desc()).first()

        return jsonify({
            'success': True,
            'kpis': {
                'total_farms':          total_farms,
                'total_area_ha':        round(float(total_area), 2),
                'total_subcounties':    total_subcounties,
                'total_wards':          total_wards,
                'farms_monitored_30d':  farms_monitored,
                'monitoring_rate_pct':  round(farms_monitored / total_farms * 100, 1) if total_farms else 0,
                'avg_health_score':     round(float(avg_health), 1) if avg_health else None,
                'top_crop':             top_crop.crop_type if top_crop else None,
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500