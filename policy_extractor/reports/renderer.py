"""fpdf2-based PDF renderer for poliza reports.

Per D-05: Letter paper size (8.5x11 inches).
Per D-07: Sections in order: header, general info, financial, asegurados, coberturas, campos_adicionales.
Per D-10: Per-insurer config controls brand_color, field_order, section toggles.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from fpdf import FPDF

from policy_extractor.reports.config_loader import load_insurer_config

# Human-readable Spanish labels for known Poliza fields
_FIELD_LABELS: dict[str, str] = {
    "numero_poliza": "Numero de Poliza",
    "nombre_contratante": "Contratante",
    "tipo_seguro": "Tipo de Seguro",
    "aseguradora": "Aseguradora",
    "fecha_emision": "Fecha de Emision",
    "inicio_vigencia": "Inicio de Vigencia",
    "fin_vigencia": "Fin de Vigencia",
    "nombre_agente": "Agente",
}


def _fmt_value(value: Any) -> str:
    """Format a field value for display in the report."""
    if value is None:
        return "N/D"
    if isinstance(value, Decimal):
        return f"{value:,.2f}"
    return str(value)


class PolizaReportPDF(FPDF):
    """fpdf2 PDF subclass that renders a structured poliza report.

    One instance per report call — FPDF is stateful, not thread-safe.
    """

    def __init__(self, poliza: Any, config: dict) -> None:
        """Initialize PDF with Letter paper and store poliza + config.

        Args:
            poliza: Poliza ORM instance (or mock) with all fields.
            config: Per-insurer config dict from load_insurer_config().
        """
        super().__init__(orientation="P", unit="mm", format="Letter")
        self._poliza = poliza
        self._config = config
        self.set_auto_page_break(auto=True, margin=15)
        # Use built-in helvetica — supports Latin/Spanish characters (accented vowels, n-tilde)
        # without needing external TTF font files.
        self._font_family = "helvetica"

    def header(self) -> None:
        """Draw insurer-branded header bar at top of each page."""
        color = self._config.get("brand_color", [50, 50, 50])
        self.set_fill_color(*color)
        # Draw colored rectangle across page header (216mm = Letter width - margins)
        self.rect(0, 0, 216, 20, style="F")
        # White bold text
        self.set_text_color(255, 255, 255)
        self.set_font(self._font_family, style="B", size=11)
        display_name = self._config.get("display_name", "Aseguradora")
        aseguradora = getattr(self._poliza, "aseguradora", "")
        header_text = f"{display_name}  |  {aseguradora.upper()}"
        self.set_xy(5, 6)
        self.cell(text=header_text)
        # Reset text color to black
        self.set_text_color(0, 0, 0)
        self.ln(20)

    def footer(self) -> None:
        """Render page number at bottom center."""
        self.set_y(-15)
        self.set_font(self._font_family, style="I", size=8)
        self.set_text_color(128, 128, 128)
        self.cell(text=f"Pagina {self.page_no()}/{{nb}}", align="C", center=True)
        self.set_text_color(0, 0, 0)

    def render(self) -> bytearray:
        """Render all sections and return PDF bytes.

        Returns:
            bytearray: Complete PDF file content.
        """
        self.alias_nb_pages()
        self.add_page()
        # Advance past header area
        self.set_y(25)
        self._render_general_info()
        self._render_financial_summary()
        self._render_asegurados_table()
        self._render_coberturas_table()
        self._render_campos_adicionales()
        return self.output()

    # ------------------------------------------------------------------
    # Section renderers
    # ------------------------------------------------------------------

    def _section_title(self, title: str) -> None:
        """Render a bold section title with bottom margin."""
        self.set_font(self._font_family, style="B", size=11)
        self.set_fill_color(240, 240, 240)
        self.cell(
            text=f"  {title}",
            w=0,
            h=8,
            fill=True,
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(2)

    def _label_value_row(self, label: str, value: str) -> None:
        """Render a single label: value row."""
        self.set_font(self._font_family, style="B", size=9)
        self.cell(text=f"{label}: ", w=55)
        self.set_font(self._font_family, size=9)
        self.multi_cell(text=value, w=0, new_x="LMARGIN", new_y="NEXT")

    def _render_general_info(self) -> None:
        """Render general info block — fields from config field_order."""
        self._section_title("Informacion General")
        field_order = self._config.get("field_order", [])
        poliza = self._poliza
        for field in field_order:
            value = getattr(poliza, field, None)
            if value is None:
                continue
            label = _FIELD_LABELS.get(field, field.replace("_", " ").title())
            self._label_value_row(label, _fmt_value(value))
        self.ln(4)

    def _render_financial_summary(self) -> None:
        """Render financial summary section."""
        self._section_title("Resumen Financiero")
        poliza = self._poliza
        prima = getattr(poliza, "prima_total", None)
        moneda = getattr(poliza, "moneda", "MXN")
        forma_pago = getattr(poliza, "forma_pago", None)
        frecuencia = getattr(poliza, "frecuencia_pago", None)

        prima_str = _fmt_value(prima) if prima is not None else "N/D"
        self._label_value_row("Prima Total", f"{prima_str} {moneda}")
        if forma_pago:
            self._label_value_row("Forma de Pago", str(forma_pago))
        if frecuencia:
            self._label_value_row("Frecuencia de Pago", str(frecuencia))
        self.ln(4)

    def _render_asegurados_table(self) -> None:
        """Render asegurados as a table if section is enabled."""
        config = self._config
        if not config.get("sections", {}).get("asegurados", True):
            return

        self._section_title("Asegurados")
        asegurados = getattr(self._poliza, "asegurados", [])

        if not asegurados:
            self.set_font(self._font_family, style="I", size=9)
            self.cell(text="Sin asegurados registrados", new_x="LMARGIN", new_y="NEXT")
            self.ln(4)
            return

        self.set_font(self._font_family, size=9)
        with self.table(first_row_as_headings=True) as table:
            # Header row
            hdr = table.row()
            hdr.cell("Nombre")
            hdr.cell("Parentesco")
            hdr.cell("Fecha Nac.")
            hdr.cell("RFC")
            # Data rows
            for aseg in asegurados:
                row = table.row()
                row.cell(_fmt_value(getattr(aseg, "nombre_descripcion", None)))
                row.cell(_fmt_value(getattr(aseg, "parentesco", None)))
                row.cell(_fmt_value(getattr(aseg, "fecha_nacimiento", None)))
                row.cell(_fmt_value(getattr(aseg, "rfc", None)))
        self.ln(4)

    def _render_coberturas_table(self) -> None:
        """Render coberturas as a table if section is enabled."""
        config = self._config
        if not config.get("sections", {}).get("coberturas", True):
            return

        self._section_title("Coberturas")
        coberturas = getattr(self._poliza, "coberturas", [])

        if not coberturas:
            self.set_font(self._font_family, style="I", size=9)
            self.cell(text="Sin coberturas registradas", new_x="LMARGIN", new_y="NEXT")
            self.ln(4)
            return

        self.set_font(self._font_family, size=9)
        with self.table(first_row_as_headings=True) as table:
            hdr = table.row()
            hdr.cell("Cobertura")
            hdr.cell("Suma Asegurada")
            hdr.cell("Deducible")
            hdr.cell("Moneda")
            for cob in coberturas:
                row = table.row()
                row.cell(_fmt_value(getattr(cob, "nombre_cobertura", None)))
                row.cell(_fmt_value(getattr(cob, "suma_asegurada", None)))
                row.cell(_fmt_value(getattr(cob, "deducible", None)))
                row.cell(_fmt_value(getattr(cob, "moneda", None)))
        self.ln(4)

    def _render_campos_adicionales(self) -> None:
        """Render campos_adicionales as key-value list.

        Per D-09: Always show section, even if empty (show 'Sin campos adicionales').
        """
        config = self._config
        if not config.get("sections", {}).get("campos_adicionales", True):
            return

        self._section_title("Campos Adicionales")
        campos = getattr(self._poliza, "campos_adicionales", None)

        if not campos:
            self.set_font(self._font_family, style="I", size=9)
            self.cell(text="Sin campos adicionales", new_x="LMARGIN", new_y="NEXT")
            self.ln(4)
            return

        for key, value in campos.items():
            label = str(key).replace("_", " ").title()
            self._label_value_row(label, _fmt_value(value))
        self.ln(4)
