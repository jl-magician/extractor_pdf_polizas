# Extractor PDF Pólizas

## What This Is

Sistema de extracción inteligente de información de pólizas de seguros en formato PDF. Utiliza IA (Claude API) para interpretar y extraer datos estructurados de pólizas provenientes de ~10 aseguradoras diferentes, cada una con 5-7 tipos de seguros (~50-70 estructuras de PDF distintas). Diseñado para una oficina de agentes de seguros que procesa más de 200 pólizas mensuales de forma manual.

## Core Value

Extraer automáticamente toda la información posible de cualquier póliza de seguro en PDF — sin importar la aseguradora o estructura — y almacenarla de forma estructurada para consulta, reporteo e integración con otros sistemas.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Extracción de datos de PDFs de pólizas usando Claude API (texto digital y escaneados con OCR)
- [ ] Soporte para PDFs en español e inglés
- [ ] Extracción flexible que se adapte a las ~50-70 estructuras diferentes sin templates fijos
- [ ] Captura de todos los datos posibles: contratante, asegurado(s), costo, coberturas, sumas aseguradas, compañía, vigencia, agente, forma de pago, deducibles, etc.
- [ ] Manejo de múltiples asegurados (personas o bienes) por póliza
- [ ] Base de datos local para almacenar toda la información extraída
- [ ] API/JSON para exponer los datos estructurados
- [ ] Interfaz de línea de comandos para procesar PDFs individual o en lote
- [ ] Esquema de datos dinámico que soporte campos variables por tipo de póliza/aseguradora

### Out of Scope

- Exportación a Excel — v2, se construirá sobre la base de datos
- Generación de reportes PDF — v2, se construirá sobre la base de datos
- Interfaz web — v2+, primero se valida la extracción y almacenamiento local
- Aplicación móvil — fuera de alcance por ahora
- Edición manual de datos extraídos en UI — v2+
- Integración directa con sistemas de aseguradoras — fuera de alcance

## Context

- Oficina de agentes de seguros en México que trabaja con 10 aseguradoras
- Cada aseguradora tiene 5-7 tipos de seguros (auto, vida, gastos médicos, hogar, etc.)
- Actualmente todo el proceso de extracción es manual: alguien lee cada PDF y copia datos
- Los PDFs son mixtos: algunos son texto digital seleccionable, otros son imágenes escaneadas
- El volumen es de más de 200 pólizas nuevas por mes
- A futuro, los datos extraídos servirán como base para un sistema propio de gestión de pólizas
- Los PDFs están en español principalmente, con algunos en inglés

## Constraints

- **LLM Provider**: Claude API (Anthropic) — el usuario ya tiene acceso
- **Plataforma inicial**: Windows 11, aplicación local de escritorio/CLI
- **PDFs mixtos**: Debe soportar tanto texto digital como imágenes escaneadas (OCR necesario)
- **Idioma**: Soporte para español e inglés en los PDFs
- **Escalabilidad**: Debe manejar 200+ pólizas/mes con tiempos razonables
- **Almacenamiento**: Base de datos local, con capacidad de exportar a JSON para integración futura

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Claude API para extracción | Usuario ya tiene API key; Claude maneja bien documentos complejos y multilingües | — Pending |
| IA sin templates fijos | 50-70 estructuras diferentes hacen insostenible mantener templates; IA se adapta automáticamente | — Pending |
| Local-first, web después | Validar la extracción antes de invertir en infraestructura web | — Pending |
| BD + JSON/API como v1 | Base sólida sobre la cual construir Excel/reportes/web después | — Pending |

---
*Last updated: 2026-03-17 after initialization*
