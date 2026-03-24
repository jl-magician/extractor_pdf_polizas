"""PDF report generation for poliza data (Phase 16).

Exports:
    generate_poliza_report(poliza) -> bytearray
"""
from policy_extractor.reports.config_loader import load_insurer_config
from policy_extractor.reports.renderer import PolizaReportPDF


def generate_poliza_report(poliza) -> bytearray:
    """Generate a PDF report for a poliza.

    Creates a new PolizaReportPDF instance per call (thread-safe via run_in_executor).
    Uses per-insurer YAML config for branding and layout.

    Args:
        poliza: Poliza ORM instance with loaded asegurados and coberturas relationships.

    Returns:
        bytearray: PDF file content starting with b'%PDF-'.
    """
    config = load_insurer_config(poliza.aseguradora)
    pdf = PolizaReportPDF(poliza, config)
    return pdf.render()
