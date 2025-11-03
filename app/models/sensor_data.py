from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class SensorData(Base):
    __tablename__ = "datos_sensores"

    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(String, ForeignKey("estacion.codigo"), index=True)
    temperatura = Column(Float)
    humedad = Column(Float)
    lluvia = Column(Float)
    fecha = Column(DateTime, index=True)
    velocidad_viento = Column(Float)
    direccion_viento = Column(Float)
    rafaga_viento = Column(Float)
    presion_barometrica = Column(Float)

    # relación con la tabla estacion
    sensor = relationship("Estacion", back_populates="datos")


class Estacion(Base):
    __tablename__ = "estacion"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, index=True, nullable=False)
    modelo = Column(String)
    nombre = Column(String)
    ubicacion = Column(String)
    latitud = Column(Float)
    longitud = Column(Float)
    descripcion = Column(String)

    # relación inversa
    datos = relationship("SensorData", back_populates="sensor")
