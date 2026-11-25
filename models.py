import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

class ReniecVerificationRequest(BaseModel):
    dni: str = Field(..., description="DNI peruano de 8 dígitos numéricos")
    consentimiento_titular: bool = Field(..., description="Consentimiento expreso del titular de los datos")

    @field_validator("dni")
    @classmethod
    def validate_dni(cls, v: str) -> str:
        clean = re.sub(r"\D", "", v.strip())
        if len(clean) != 8:
            raise ValueError("El DNI debe contener exactamente 8 dígitos numéricos.")
        return clean

class ReniecVerificationResponse(BaseModel):
    success: bool
    verificado_oficial: bool
    mensaje: str
    dni: str
    nombres: Optional[str] = ""
    apellido_paterno: Optional[str] = ""
    apellido_materno: Optional[str] = ""
    digito_verificador: Optional[int] = None
    proveedor: Optional[str] = ""
    advertencia_legal: str
    permite_llenado_manual: bool = True

class EnvioCreateRequest(BaseModel):
    tipo_documento: str = Field(default="DNI", description="DNI o CE")
    dni: str = Field(..., description="DNI de 8 dígitos o CE de 8-12 dígitos")
    nombres: str = Field(..., min_length=2, max_length=100)
    apellido_paterno: str = Field(..., min_length=2, max_length=100)
    apellido_materno: str = Field(..., min_length=2, max_length=100)
    celular: str = Field(..., description="Número de celular peruano de 9 dígitos que inicia con 9")
    
    # Ubicación y Agencia de destino Shalom
    departamento: str = Field(..., min_length=2, max_length=60)
    provincia: str = Field(..., min_length=2, max_length=60)
    distrito: str = Field(..., min_length=2, max_length=60)
    codigo_agencia: str = Field(..., min_length=1, max_length=50)
    nombre_agencia: str = Field(..., min_length=2, max_length=150)
    direccion_agencia: str = Field(..., min_length=5)
    referencia_agencia: Optional[str] = ""
    
    # Fecha de despacho deseada
    fecha_despacho: Optional[str] = ""
    
    # Tamaño de mercadería Shalom Pro (Default: PAQUETE XS)
    tamano_paquete: Optional[str] = Field(default="PAQUETE XS", description="SOBRE, PAQUETE XXS, PAQUETE XS, PAQUETE S, PAQUETE M, PAQUETE L")

    # Estado de verificación
    estado_verificacion_identidad: str = Field(
        default="MANUAL_NO_VERIFICADO",
        description="VERIFICADO_RENIEC_OFICIAL o MANUAL_NO_VERIFICADO"
    )
    
    # Token de idempotencia para prevenir duplicados y doble clic accidental
    idempotency_key: str = Field(..., min_length=10, max_length=64)

    @field_validator("tipo_documento")
    @classmethod
    def validate_tipo_doc(cls, v: str) -> str:
        t = v.strip().upper()
        if t not in ("DNI", "CE"):
            return "DNI"
        return t

    @field_validator("dni")
    @classmethod
    def validate_documento(cls, v: str, info) -> str:
        tipo = info.data.get("tipo_documento", "DNI") if hasattr(info, "data") else "DNI"
        clean = v.strip().upper()
        if tipo == "DNI":
            digitos = re.sub(r"\D", "", clean)
            if len(digitos) != 8:
                raise ValueError("El DNI peruano debe tener exactamente 8 dígitos numéricos.")
            return digitos
        else:
            clean_ce = re.sub(r"[^A-Z0-9]", "", clean)
            if len(clean_ce) < 8 or len(clean_ce) > 12:
                raise ValueError("El Carnet de Extranjería debe tener entre 8 y 12 caracteres alfanuméricos.")
            return clean_ce

    @field_validator("celular")
    @classmethod
    def validate_celular(cls, v: str) -> str:
        clean = re.sub(r"\D", "", v.strip())
        if len(clean) != 9:
            raise ValueError("El número celular peruano debe contener exactamente 9 dígitos.")
        if not clean.startswith("9"):
            raise ValueError("El número celular peruano debe iniciar con el dígito 9.")
        return clean

class EnvioStatusUpdateRequest(BaseModel):
    estado_registro: str = Field(..., description="PENDIENTE, CONFIRMADO, EN_PREPARACION, ENVIADO, ENTREGADO, CANCELADO")
    notas_admin: Optional[str] = None

class EnvioTamanoUpdateRequest(BaseModel):
    tamano_paquete: str = Field(..., description="SOBRE, PAQUETE XXS, PAQUETE XS, PAQUETE S, PAQUETE M, PAQUETE L")

    @field_validator("tamano_paquete")
    @classmethod
    def validate_tamano(cls, v: str) -> str:
        t = v.strip().upper()
        permitidos = ["SOBRE", "PAQUETE XXS", "PAQUETE XS", "PAQUETE S", "PAQUETE M", "PAQUETE L"]
        if t not in permitidos:
            raise ValueError(f"Tamaño inválido. Debe ser uno de: {', '.join(permitidos)}")
        return t

class AdminLoginRequest(BaseModel):
    username: str
    password: str

class AgenciaToggleRequest(BaseModel):
    activo: bool
    motivo: Optional[str] = ""

class AgenciaImportRequest(BaseModel):
    contenido: str
    formato: Optional[str] = "auto"
    fuente: Optional[str] = ""
    dry_run: bool = True
    forzar: bool = False

# ==============================================================================
# MODELOS PARA SHALOM PRO
# ==============================================================================
class ShalomProEmitirRequest(BaseModel):
    contenido_paquete: Optional[str] = Field(default="PAQUETE / MERCADERÍA", description="Descripción del contenido")
    bultos: Optional[int] = Field(default=1, ge=1, le=50, description="Cantidad de bultos")
    peso_kg: Optional[float] = Field(default=1.0, ge=0.1, le=100.0, description="Peso estimado en kg")
    tipo_pago: Optional[str] = Field(default="PAGO_EN_DESTINO", description="PAGO_EN_DESTINO o PAGADO")
    observaciones: Optional[str] = ""
