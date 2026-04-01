"""
core/models.py
--------------
SQLAlchemy ORM models with PostGIS geometry support.
"""
import uuid as _uuid_mod
from datetime import datetime
from geoalchemy2 import Geometry
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from extensions import db


class TimestampMixin:
    """Adds created_at and updated_at to any model."""
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Subcounty ─────────────────────────────────────────────────────────────────

class Subcounty(TimestampMixin, db.Model):
    __tablename__ = 'subcounties'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    code        = db.Column(db.String(20))
    description = db.Column(db.Text)
    geom        = db.Column(Geometry(geometry_type='MULTIPOLYGON', srid=4326))

    wards = db.relationship('Ward', backref='subcounty', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id':          self.id,
            'name':        self.name,
            'code':        self.code,
            'description': self.description,
            'created_at':  self.created_at.isoformat() if self.created_at else None,
        }

    def to_geojson(self):
        return {
            'type': 'Feature',
            'geometry': db.session.scalar(func.ST_AsGeoJSON(self.geom)) if self.geom else None,
            'properties': self.to_dict()
        }


# ── Ward ──────────────────────────────────────────────────────────────────────

class Ward(TimestampMixin, db.Model):
    __tablename__ = 'wards'

    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(100), nullable=False)
    subcounty_id = db.Column(db.Integer, db.ForeignKey('subcounties.id', ondelete='CASCADE'), nullable=False)
    code         = db.Column(db.String(20))
    population   = db.Column(db.Integer, default=0)
    area_sq_km   = db.Column(db.Numeric(10, 4), default=0)
    geom         = db.Column(Geometry(geometry_type='MULTIPOLYGON', srid=4326))

    farms = db.relationship('Farm', backref='ward', lazy='dynamic')

    def to_dict(self):
        return {
            'id':           self.id,
            'name':         self.name,
            'subcounty_id': self.subcounty_id,
            'code':         self.code,
            'population':   self.population,
            'area_sq_km':   float(self.area_sq_km) if self.area_sq_km else 0,
            'created_at':   self.created_at.isoformat() if self.created_at else None,
        }

    def to_geojson(self):
        return {
            'type': 'Feature',
            'geometry': db.session.scalar(func.ST_AsGeoJSON(self.geom)) if self.geom else None,
            'properties': self.to_dict()
        }


# ── Map Layer ─────────────────────────────────────────────────────────────────

class MapLayer(TimestampMixin, db.Model):
    __tablename__ = 'map_layers'

    id          = db.Column(db.Integer, primary_key=True)
    uuid        = db.Column(UUID(as_uuid=True), default=_uuid_mod.uuid4, unique=True, nullable=False)
    name        = db.Column(db.String(200), nullable=False)
    color       = db.Column(db.String(20), default='#3b82f6')
    visible     = db.Column(db.Boolean, default=True)
    description = db.Column(db.String(500))
    farm_count  = db.Column(db.Integer, default=0)

    farms = db.relationship('Farm', backref='layer', lazy='dynamic',
                            foreign_keys='Farm.layer_id')

    def to_dict(self):
        return {
            'id':          self.id,
            'uuid':        str(self.uuid) if self.uuid else None,
            'name':        self.name,
            'color':       self.color,
            'visible':     self.visible,
            'description': self.description,
            'farm_count':  self.farms.count(),
            'created_at':  self.created_at.isoformat() if self.created_at else None,
        }


# ── Farm ──────────────────────────────────────────────────────────────────────

class Farm(TimestampMixin, db.Model):
    __tablename__ = 'farms'

    id                  = db.Column(db.Integer, primary_key=True)
    name                = db.Column(db.String(200), nullable=False)
    crop_type           = db.Column(db.String(100))
    planting_date       = db.Column(db.Date)
    area_ha             = db.Column(db.Numeric(10, 4))
    latitude            = db.Column(db.Numeric(10, 7))
    longitude           = db.Column(db.Numeric(10, 7))
    location            = db.Column(Geometry(geometry_type='POINT', srid=4326))
    # Geometry type left as generic so both Polygon + MultiPolygon are accepted
    boundary            = db.Column(Geometry(geometry_type='GEOMETRY', srid=4326))
    soil_type           = db.Column(db.String(100))
    irrigation          = db.Column(db.String(100))
    fertilizer_used     = db.Column(db.String(200))
    yield_estimate_tons = db.Column(db.Numeric(10, 4))
    status              = db.Column(db.String(50), default='active')
    ward_id             = db.Column(db.Integer, db.ForeignKey('wards.id'))
    layer_id            = db.Column(db.Integer, db.ForeignKey('map_layers.id', ondelete='SET NULL'), nullable=True)

    # Original attributes from the uploaded boundary file stored as-is
    attributes          = db.Column(JSONB, default=dict)

    # Relationships
    ndvi_readings     = db.relationship('NDVIReading',     backref='farm', lazy='dynamic', cascade='all, delete-orphan')
    moisture_readings = db.relationship('MoistureReading', backref='farm', lazy='dynamic', cascade='all, delete-orphan')
    recommendations   = db.relationship('Recommendation',  backref='farm', lazy='dynamic', cascade='all, delete-orphan')
    satellite_imagery = db.relationship('SatelliteImagery',backref='farm', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id':                  self.id,
            'name':                self.name,
            'crop_type':           self.crop_type,
            'planting_date':       str(self.planting_date) if self.planting_date else None,
            'area_ha':             float(self.area_ha) if self.area_ha else None,
            'latitude':            float(self.latitude) if self.latitude else None,
            'longitude':           float(self.longitude) if self.longitude else None,
            'soil_type':           self.soil_type,
            'irrigation':          self.irrigation,
            'fertilizer_used':     self.fertilizer_used,
            'yield_estimate_tons': float(self.yield_estimate_tons) if self.yield_estimate_tons else None,
            'status':              self.status,
            'ward_id':             self.ward_id,
            'layer_id':            self.layer_id,
            'attributes':          self.attributes or {},
            'created_at':          self.created_at.isoformat() if self.created_at else None,
        }

    def to_geojson(self):
        geom  = self.boundary or self.location
        props = self.to_dict()
        props['has_boundary'] = self.boundary is not None
        return {
            'type':     'Feature',
            'geometry': __import__('json').loads(db.session.scalar(func.ST_AsGeoJSON(geom))) if geom else None,
            'properties': props,
        }


# ── NDVI Reading ──────────────────────────────────────────────────────────────

class NDVIReading(db.Model):
    __tablename__ = 'ndvi_readings'

    id           = db.Column(db.Integer, primary_key=True)
    farm_id      = db.Column(db.Integer, db.ForeignKey('farms.id', ondelete='CASCADE'))
    date         = db.Column(db.Date, nullable=False)
    ndvi_value   = db.Column(db.Numeric(6, 4))
    health_score = db.Column(db.Integer)
    status       = db.Column(db.String(50))
    source       = db.Column(db.String(50), default='sentinel-2')
    created_at   = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':           self.id,
            'farm_id':      self.farm_id,
            'date':         str(self.date),
            'ndvi_value':   float(self.ndvi_value) if self.ndvi_value else None,
            'health_score': self.health_score,
            'status':       self.status,
            'source':       self.source,
        }


# ── Moisture Reading ──────────────────────────────────────────────────────────

class MoistureReading(db.Model):
    __tablename__ = 'moisture_readings'

    id                = db.Column(db.Integer, primary_key=True)
    farm_id           = db.Column(db.Integer, db.ForeignKey('farms.id', ondelete='CASCADE'))
    date              = db.Column(db.Date, nullable=False)
    moisture_percent  = db.Column(db.Numeric(6, 2))
    status            = db.Column(db.String(50))
    days_since_rain   = db.Column(db.Integer)
    created_at        = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':               self.id,
            'farm_id':          self.farm_id,
            'date':             str(self.date),
            'moisture_percent': float(self.moisture_percent) if self.moisture_percent else None,
            'status':           self.status,
            'days_since_rain':  self.days_since_rain,
        }


# ── Weather Data ──────────────────────────────────────────────────────────────

class WeatherData(db.Model):
    __tablename__ = 'weather_data'

    id               = db.Column(db.Integer, primary_key=True)
    latitude         = db.Column(db.Numeric(10, 7))
    longitude        = db.Column(db.Numeric(10, 7))
    location         = db.Column(Geometry(geometry_type='POINT', srid=4326))
    date             = db.Column(db.Date, nullable=False)
    temperature      = db.Column(db.Numeric(5, 2))
    humidity         = db.Column(db.Integer)
    rain_probability = db.Column(db.Integer)
    rain_amount      = db.Column(db.Numeric(6, 2))
    conditions       = db.Column(db.String(100))
    source           = db.Column(db.String(50), default='openweather')
    created_at       = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':               self.id,
            'latitude':         float(self.latitude) if self.latitude else None,
            'longitude':        float(self.longitude) if self.longitude else None,
            'date':             str(self.date),
            'temperature':      float(self.temperature) if self.temperature else None,
            'humidity':         self.humidity,
            'rain_probability': self.rain_probability,
            'rain_amount':      float(self.rain_amount) if self.rain_amount else None,
            'conditions':       self.conditions,
            'source':           self.source,
        }


# ── Recommendation ────────────────────────────────────────────────────────────

class Recommendation(db.Model):
    __tablename__ = 'recommendations'

    id          = db.Column(db.Integer, primary_key=True)
    farm_id     = db.Column(db.Integer, db.ForeignKey('farms.id', ondelete='CASCADE'))
    priority    = db.Column(db.String(20))
    action      = db.Column(db.Text, nullable=False)
    reason      = db.Column(db.Text)
    category    = db.Column(db.String(50))
    is_resolved = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':          self.id,
            'farm_id':     self.farm_id,
            'priority':    self.priority,
            'action':      self.action,
            'reason':      self.reason,
            'category':    self.category,
            'is_resolved': self.is_resolved,
            'created_at':  self.created_at.isoformat() if self.created_at else None,
        }


# ── Market ────────────────────────────────────────────────────────────────────

class Market(TimestampMixin, db.Model):
    __tablename__ = 'markets'

    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(200), nullable=False)
    location_text  = db.Column(db.String(200))
    latitude       = db.Column(db.Numeric(10, 7))
    longitude      = db.Column(db.Numeric(10, 7))
    location       = db.Column(Geometry(geometry_type='POINT', srid=4326))
    contact_phone  = db.Column(db.String(50))
    contact_person = db.Column(db.String(100))
    operating_days = db.Column(db.String(200))
    payment_terms  = db.Column(db.String(200))
    is_active      = db.Column(db.Boolean, default=True)

    prices = db.relationship('MarketPrice', backref='market', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id':             self.id,
            'name':           self.name,
            'location':       self.location_text,
            'latitude':       float(self.latitude) if self.latitude else None,
            'longitude':      float(self.longitude) if self.longitude else None,
            'contact_phone':  self.contact_phone,
            'contact_person': self.contact_person,
            'operating_days': self.operating_days,
            'payment_terms':  self.payment_terms,
            'is_active':      self.is_active,
        }


# ── Market Price ──────────────────────────────────────────────────────────────

class MarketPrice(TimestampMixin, db.Model):
    __tablename__ = 'market_prices'

    id            = db.Column(db.Integer, primary_key=True)
    market_id     = db.Column(db.Integer, db.ForeignKey('markets.id', ondelete='CASCADE'), nullable=False)
    crop_type     = db.Column(db.String(100), nullable=False)
    price         = db.Column(db.Numeric(10, 2), nullable=False)
    unit          = db.Column(db.String(50), default='per 90kg bag')
    grade         = db.Column(db.String(50))
    date_recorded = db.Column(db.Date)
    is_current    = db.Column(db.Boolean, default=True)
    notes         = db.Column(db.Text)

    def to_dict(self):
        return {
            'id':            self.id,
            'market_id':     self.market_id,
            'crop_type':     self.crop_type,
            'price':         float(self.price),
            'unit':          self.unit,
            'grade':         self.grade,
            'date_recorded': str(self.date_recorded) if self.date_recorded else None,
            'is_current':    self.is_current,
            'notes':         self.notes,
        }


# ── Collection Center ─────────────────────────────────────────────────────────

class CollectionCenter(TimestampMixin, db.Model):
    __tablename__ = 'collection_centers'

    id                   = db.Column(db.Integer, primary_key=True)
    name                 = db.Column(db.String(200), nullable=False)
    location_text        = db.Column(db.String(200))
    latitude             = db.Column(db.Numeric(10, 7))
    longitude            = db.Column(db.Numeric(10, 7))
    location             = db.Column(Geometry(geometry_type='POINT', srid=4326))
    crops_accepted       = db.Column(db.Text)
    contact_phone        = db.Column(db.String(50))
    contact_person       = db.Column(db.String(100))
    operating_days       = db.Column(db.String(200))
    operating_hours      = db.Column(db.String(100))
    storage_capacity     = db.Column(db.String(100))
    payment_terms        = db.Column(db.String(200))
    minimum_quantity     = db.Column(db.String(100))
    quality_requirements = db.Column(db.Text)
    is_active            = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id':                   self.id,
            'name':                 self.name,
            'location':             self.location_text,
            'latitude':             float(self.latitude) if self.latitude else None,
            'longitude':            float(self.longitude) if self.longitude else None,
            'crops_accepted':       self.crops_accepted,
            'contact_phone':        self.contact_phone,
            'contact_person':       self.contact_person,
            'operating_days':       self.operating_days,
            'operating_hours':      self.operating_hours,
            'storage_capacity':     self.storage_capacity,
            'payment_terms':        self.payment_terms,
            'minimum_quantity':     self.minimum_quantity,
            'quality_requirements': self.quality_requirements,
            'is_active':            self.is_active,
        }


# ── Satellite Imagery ─────────────────────────────────────────────────────────

class SatelliteImagery(db.Model):
    __tablename__ = 'satellite_imagery'

    id             = db.Column(db.Integer, primary_key=True)
    farm_id        = db.Column(db.Integer, db.ForeignKey('farms.id', ondelete='CASCADE'))
    date_acquired  = db.Column(db.Date, nullable=False)
    satellite      = db.Column(db.String(50))
    cloud_cover    = db.Column(db.Numeric(5, 2))
    ndvi           = db.Column(db.Numeric(6, 4))
    evi            = db.Column(db.Numeric(6, 4))
    moisture_index = db.Column(db.Numeric(6, 4))
    raw_data       = db.Column(db.JSON)
    created_at     = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':             self.id,
            'farm_id':        self.farm_id,
            'date_acquired':  str(self.date_acquired),
            'satellite':      self.satellite,
            'cloud_cover':    float(self.cloud_cover) if self.cloud_cover else None,
            'ndvi':           float(self.ndvi) if self.ndvi else None,
            'evi':            float(self.evi) if self.evi else None,
            'moisture_index': float(self.moisture_index) if self.moisture_index else None,
        }