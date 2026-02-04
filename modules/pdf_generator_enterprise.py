#!/usr/bin/env python3
"""
Enterprise PDF Report Generator
ReviewSignal 5.1.0

Professional-grade PDF generation with:
- White-label branding (client logos, custom colors)
- Executive Summary with KPI Dashboard
- AI-powered recommendations
- Interactive Table of Contents with bookmarks
- Industry benchmarks & competitor comparison
- Advanced charts (gauges, sparklines, heatmaps)
- Premium typography and visual hierarchy

Author: ReviewSignal Analytics Team
Version: 2.0 Enterprise
"""

import io
import math
import structlog
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Union
from collections import defaultdict

# ReportLab imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate,
    BaseDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
    Image,
    KeepTogether,
    Frame,
    PageTemplate,
    NextPageTemplate,
    Flowable,
    ListFlowable,
    ListItem,
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle, Wedge, Group
from reportlab.graphics.charts.barcharts import VerticalBarChart, HorizontalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS & DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

class ReportType(Enum):
    SENTIMENT = "sentiment"
    ANOMALY = "anomaly"
    MONTHLY_SUMMARY = "monthly_summary"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    EXECUTIVE_BRIEFING = "executive_briefing"
    CUSTOM = "custom"


class SeverityLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class TrendDirection(Enum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


@dataclass
class BrandingConfig:
    """White-label branding configuration."""
    company_name: str = "ReviewSignal.ai"
    logo_path: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: str = "#1E3A5F"  # Deep navy blue
    secondary_color: str = "#4A90D9"  # Sky blue
    accent_color: str = "#2ECC71"  # Green for positive
    warning_color: str = "#E74C3C"  # Red for negative
    neutral_color: str = "#95A5A6"  # Gray
    font_family: str = "Helvetica"
    tagline: Optional[str] = "Alternative Data Intelligence"
    website: Optional[str] = "reviewsignal.ai"
    contact_email: Optional[str] = None

    def get_color(self, name: str) -> colors.Color:
        """Get color object by name."""
        color_map = {
            "primary": self.primary_color,
            "secondary": self.secondary_color,
            "accent": self.accent_color,
            "warning": self.warning_color,
            "neutral": self.neutral_color,
        }
        hex_color = color_map.get(name, self.primary_color)
        return colors.HexColor(hex_color)


@dataclass
class KPICard:
    """KPI card for executive dashboard."""
    title: str
    value: Union[str, int, float]
    unit: str = ""
    trend: Optional[TrendDirection] = None
    trend_value: Optional[float] = None
    benchmark: Optional[float] = None
    benchmark_label: str = "Industry Avg"
    severity: SeverityLevel = SeverityLevel.INFO
    description: Optional[str] = None

    def format_value(self) -> str:
        """Format value for display."""
        if isinstance(self.value, float):
            if self.unit == "%":
                return f"{self.value:.1f}%"
            return f"{self.value:,.2f}"
        elif isinstance(self.value, int):
            return f"{self.value:,}"
        return str(self.value)


@dataclass
class Recommendation:
    """AI-powered recommendation."""
    title: str
    description: str
    priority: SeverityLevel = SeverityLevel.MEDIUM
    impact: str = "Medium"
    effort: str = "Medium"
    category: str = "General"
    data_points: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)


@dataclass
class BenchmarkData:
    """Industry benchmark comparison data."""
    metric_name: str
    your_value: float
    industry_avg: float
    industry_best: float
    percentile: int  # Your percentile ranking (0-100)
    trend: TrendDirection = TrendDirection.STABLE


@dataclass
class CompetitorData:
    """Competitor comparison data."""
    name: str
    sentiment_score: float
    review_count: int
    avg_rating: float
    trend: TrendDirection
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)


@dataclass
class EnterpriseReportData:
    """Complete data structure for enterprise reports."""
    # Basic info
    client_name: str
    report_title: str
    report_period: str
    generated_at: datetime = field(default_factory=datetime.now)

    # KPIs
    kpis: List[KPICard] = field(default_factory=list)

    # Sentiment data
    overall_sentiment: str = "Neutral"
    sentiment_score: float = 0.0
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    total_reviews: int = 0

    # Trends
    sentiment_trend: List[Tuple[str, float]] = field(default_factory=list)
    volume_trend: List[Tuple[str, int]] = field(default_factory=list)

    # Analysis
    key_themes: List[Dict[str, Any]] = field(default_factory=list)
    top_positive_reviews: List[str] = field(default_factory=list)
    top_negative_reviews: List[str] = field(default_factory=list)

    # AI Recommendations
    recommendations: List[Recommendation] = field(default_factory=list)

    # Benchmarks
    benchmarks: List[BenchmarkData] = field(default_factory=list)

    # Competitors
    competitors: List[CompetitorData] = field(default_factory=list)

    # Locations
    location_data: List[Dict[str, Any]] = field(default_factory=list)

    # Anomalies
    anomalies: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    data_sources: List[str] = field(default_factory=list)
    locations_analyzed: int = 0
    confidence_level: float = 0.95


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM FLOWABLES
# ═══════════════════════════════════════════════════════════════════════════════

class KPICardFlowable(Flowable):
    """Custom flowable for KPI cards."""

    def __init__(self, kpi: KPICard, branding: BrandingConfig, width: float = 120, height: float = 80):
        Flowable.__init__(self)
        self.kpi = kpi
        self.branding = branding
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv

        # Card background with rounded corners
        c.setFillColor(colors.white)
        c.setStrokeColor(colors.HexColor("#E0E0E0"))
        c.roundRect(0, 0, self.width, self.height, 8, fill=1, stroke=1)

        # Severity indicator stripe
        severity_colors = {
            SeverityLevel.CRITICAL: "#E74C3C",
            SeverityLevel.HIGH: "#E67E22",
            SeverityLevel.MEDIUM: "#F1C40F",
            SeverityLevel.LOW: "#2ECC71",
            SeverityLevel.INFO: "#3498DB",
        }
        c.setFillColor(colors.HexColor(severity_colors.get(self.kpi.severity, "#3498DB")))
        c.rect(0, self.height - 6, self.width, 6, fill=1, stroke=0)

        # Title
        c.setFillColor(colors.HexColor("#7F8C8D"))
        c.setFont("Helvetica", 8)
        c.drawString(10, self.height - 22, self.kpi.title[:20])

        # Main value
        c.setFillColor(colors.HexColor(self.branding.primary_color))
        c.setFont("Helvetica-Bold", 18)
        value_str = self.kpi.format_value()
        c.drawString(10, self.height - 48, value_str)

        # Trend indicator
        if self.kpi.trend:
            trend_x = 10 + len(value_str) * 10
            if self.kpi.trend == TrendDirection.UP:
                c.setFillColor(colors.HexColor("#2ECC71"))
                c.drawString(trend_x, self.height - 48, " ▲")
            elif self.kpi.trend == TrendDirection.DOWN:
                c.setFillColor(colors.HexColor("#E74C3C"))
                c.drawString(trend_x, self.height - 48, " ▼")

            if self.kpi.trend_value:
                c.setFont("Helvetica", 9)
                c.drawString(trend_x + 15, self.height - 48, f"{self.kpi.trend_value:+.1f}%")

        # Benchmark comparison
        if self.kpi.benchmark is not None:
            c.setFillColor(colors.HexColor("#95A5A6"))
            c.setFont("Helvetica", 7)
            c.drawString(10, 12, f"{self.kpi.benchmark_label}: {self.kpi.benchmark:.1f}")


class GaugeChart(Flowable):
    """Gauge/speedometer chart for single metrics."""

    def __init__(self, value: float, min_val: float = 0, max_val: float = 100,
                 title: str = "", branding: BrandingConfig = None,
                 width: float = 150, height: float = 100):
        Flowable.__init__(self)
        self.value = value
        self.min_val = min_val
        self.max_val = max_val
        self.title = title
        self.branding = branding or BrandingConfig()
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        cx, cy = self.width / 2, self.height * 0.4
        radius = min(self.width, self.height) * 0.35

        # Draw gauge background arc
        c.setStrokeColor(colors.HexColor("#E0E0E0"))
        c.setLineWidth(15)

        # Background arc (180 degrees)
        for i in range(181):
            angle = math.radians(180 - i)
            x1 = cx + (radius - 7) * math.cos(angle)
            y1 = cy + (radius - 7) * math.sin(angle)
            x2 = cx + (radius + 7) * math.cos(angle)
            y2 = cy + (radius + 7) * math.sin(angle)

        # Colored segments
        segments = [
            (0, 30, "#E74C3C"),    # Red
            (30, 60, "#F1C40F"),   # Yellow
            (60, 100, "#2ECC71"),  # Green
        ]

        c.setLineWidth(12)
        for start_pct, end_pct, color in segments:
            c.setStrokeColor(colors.HexColor(color))
            start_angle = 180 - (start_pct / 100 * 180)
            end_angle = 180 - (end_pct / 100 * 180)
            # Draw arc segment
            for i in range(int(start_angle), int(end_angle), -1):
                angle = math.radians(i)
                x = cx + radius * math.cos(angle)
                y = cy + radius * math.sin(angle)
                c.circle(x, y, 1, fill=1, stroke=0)

        # Draw needle
        normalized = (self.value - self.min_val) / (self.max_val - self.min_val)
        needle_angle = math.radians(180 - normalized * 180)
        needle_length = radius * 0.8

        c.setStrokeColor(colors.HexColor(self.branding.primary_color))
        c.setFillColor(colors.HexColor(self.branding.primary_color))
        c.setLineWidth(2)

        end_x = cx + needle_length * math.cos(needle_angle)
        end_y = cy + needle_length * math.sin(needle_angle)
        c.line(cx, cy, end_x, end_y)
        c.circle(cx, cy, 5, fill=1, stroke=0)

        # Value text
        c.setFillColor(colors.HexColor(self.branding.primary_color))
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(cx, cy - 25, f"{self.value:.1f}")

        # Title
        if self.title:
            c.setFillColor(colors.HexColor("#7F8C8D"))
            c.setFont("Helvetica", 9)
            c.drawCentredString(cx, self.height - 15, self.title)


class SparklineChart(Flowable):
    """Mini trend chart (sparkline)."""

    def __init__(self, data: List[float], width: float = 80, height: float = 25,
                 color: str = "#3498DB", show_endpoints: bool = True):
        Flowable.__init__(self)
        self.data = data
        self.width = width
        self.height = height
        self.color = color
        self.show_endpoints = show_endpoints

    def draw(self):
        if not self.data or len(self.data) < 2:
            return

        c = self.canv

        # Normalize data
        min_val = min(self.data)
        max_val = max(self.data)
        val_range = max_val - min_val if max_val != min_val else 1

        # Calculate points
        points = []
        for i, val in enumerate(self.data):
            x = (i / (len(self.data) - 1)) * self.width
            y = ((val - min_val) / val_range) * (self.height - 4) + 2
            points.append((x, y))

        # Draw line
        c.setStrokeColor(colors.HexColor(self.color))
        c.setLineWidth(1.5)

        path = c.beginPath()
        path.moveTo(points[0][0], points[0][1])
        for x, y in points[1:]:
            path.lineTo(x, y)
        c.drawPath(path)

        # Endpoints
        if self.show_endpoints:
            # Start point
            c.setFillColor(colors.HexColor(self.color))
            c.circle(points[0][0], points[0][1], 2, fill=1, stroke=0)

            # End point (larger, different color based on trend)
            end_color = "#2ECC71" if self.data[-1] >= self.data[0] else "#E74C3C"
            c.setFillColor(colors.HexColor(end_color))
            c.circle(points[-1][0], points[-1][1], 3, fill=1, stroke=0)


class SectionHeader(Flowable):
    """Professional section header with icon and styling."""

    def __init__(self, title: str, branding: BrandingConfig, width: float = 500,
                 icon: str = None, subtitle: str = None):
        Flowable.__init__(self)
        self.title = title
        self.branding = branding
        self.width = width
        self.icon = icon
        self.subtitle = subtitle
        self.height = 40 if subtitle else 30

    def draw(self):
        c = self.canv

        # Left accent bar
        c.setFillColor(colors.HexColor(self.branding.primary_color))
        c.rect(0, 0, 4, self.height, fill=1, stroke=0)

        # Title
        c.setFillColor(colors.HexColor(self.branding.primary_color))
        c.setFont("Helvetica-Bold", 14)
        c.drawString(15, self.height - 18, self.title.upper())

        # Subtitle
        if self.subtitle:
            c.setFillColor(colors.HexColor("#7F8C8D"))
            c.setFont("Helvetica", 9)
            c.drawString(15, 8, self.subtitle)

        # Bottom line
        c.setStrokeColor(colors.HexColor("#E0E0E0"))
        c.setLineWidth(0.5)
        c.line(0, 0, self.width, 0)


class BenchmarkBar(Flowable):
    """Horizontal benchmark comparison bar."""

    def __init__(self, benchmark: BenchmarkData, branding: BrandingConfig,
                 width: float = 400, height: float = 50):
        Flowable.__init__(self)
        self.benchmark = benchmark
        self.branding = branding
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv

        bar_height = 12
        bar_y = self.height / 2 - bar_height / 2
        label_width = 120
        bar_width = self.width - label_width - 80

        # Convert to float for safety
        your_value = float(self.benchmark.your_value)
        industry_avg = float(self.benchmark.industry_avg)
        industry_best = float(self.benchmark.industry_best)

        # Label
        c.setFillColor(colors.HexColor("#2C3E50"))
        c.setFont("Helvetica", 9)
        c.drawString(0, bar_y + 2, self.benchmark.metric_name[:25])

        # Background bar
        c.setFillColor(colors.HexColor("#ECF0F1"))
        c.roundRect(label_width, bar_y, bar_width, bar_height, 3, fill=1, stroke=0)

        # Industry average marker
        if industry_avg > 0 and industry_best > 0:
            avg_x = label_width + (industry_avg / industry_best) * bar_width
            c.setStrokeColor(colors.HexColor("#95A5A6"))
            c.setLineWidth(2)
            c.line(avg_x, bar_y - 3, avg_x, bar_y + bar_height + 3)

        # Your value bar
        your_ratio = min(your_value / industry_best, 1.0) if industry_best > 0 else 0
        your_width = your_ratio * bar_width

        # Color based on performance
        if your_value >= industry_avg:
            bar_color = "#2ECC71"  # Green - above average
        else:
            bar_color = "#E74C3C"  # Red - below average

        c.setFillColor(colors.HexColor(bar_color))
        c.roundRect(label_width, bar_y, your_width, bar_height, 3, fill=1, stroke=0)

        # Value label
        c.setFillColor(colors.HexColor("#2C3E50"))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(label_width + bar_width + 10, bar_y + 2, f"{your_value:.1f}")

        # Percentile badge
        c.setFillColor(colors.HexColor(self.branding.secondary_color))
        c.roundRect(self.width - 45, bar_y - 2, 40, bar_height + 4, 3, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(self.width - 25, bar_y + 2, f"P{self.benchmark.percentile}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTERPRISE PDF GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

class EnterprisePDFGenerator:
    """
    Enterprise-grade PDF report generator.

    Features:
    - White-label branding
    - Executive dashboard with KPI cards
    - AI-powered recommendations
    - Interactive TOC with bookmarks
    - Industry benchmarks
    - Competitor analysis
    - Advanced visualizations
    """

    def __init__(
        self,
        branding: Optional[BrandingConfig] = None,
        page_size: str = "letter",
    ):
        self.branding = branding or BrandingConfig()
        self.page_size = letter if page_size == "letter" else A4
        self.width, self.height = self.page_size
        self.styles = getSampleStyleSheet()
        self._setup_enterprise_styles()
        self.toc_entries = []

        logger.info(
            "enterprise_pdf_generator_initialized",
            company=self.branding.company_name,
            page_size=page_size,
        )

    def _setup_enterprise_styles(self) -> None:
        """Configure premium typography and styles."""

        # Cover Title
        self.styles.add(ParagraphStyle(
            name='CoverTitle',
            fontName='Helvetica-Bold',
            fontSize=32,
            textColor=colors.HexColor(self.branding.primary_color),
            alignment=TA_CENTER,
            spaceAfter=20,
            leading=40,
        ))

        # Cover Subtitle
        self.styles.add(ParagraphStyle(
            name='CoverSubtitle',
            fontName='Helvetica',
            fontSize=16,
            textColor=colors.HexColor('#7F8C8D'),
            alignment=TA_CENTER,
            spaceAfter=10,
            leading=22,
        ))

        # Section Title
        self.styles.add(ParagraphStyle(
            name='SectionTitle',
            fontName='Helvetica-Bold',
            fontSize=16,
            textColor=colors.HexColor(self.branding.primary_color),
            spaceBefore=20,
            spaceAfter=12,
            leading=20,
        ))

        # Subsection Title
        self.styles.add(ParagraphStyle(
            name='SubsectionTitle',
            fontName='Helvetica-Bold',
            fontSize=12,
            textColor=colors.HexColor('#2C3E50'),
            spaceBefore=15,
            spaceAfter=8,
            leading=16,
        ))

        # Body Text
        self.styles.add(ParagraphStyle(
            name='EnterpriseBody',
            fontName='Helvetica',
            fontSize=10,
            textColor=colors.HexColor('#2C3E50'),
            alignment=TA_JUSTIFY,
            spaceAfter=10,
            leading=14,
        ))

        # Insight Box
        self.styles.add(ParagraphStyle(
            name='InsightBox',
            fontName='Helvetica-Oblique',
            fontSize=10,
            textColor=colors.HexColor(self.branding.secondary_color),
            leftIndent=20,
            rightIndent=20,
            spaceBefore=10,
            spaceAfter=10,
            leading=14,
            backColor=colors.HexColor('#F8F9FA'),
            borderWidth=1,
            borderColor=colors.HexColor(self.branding.secondary_color),
            borderPadding=10,
        ))

        # Recommendation Box
        self.styles.add(ParagraphStyle(
            name='RecommendationTitle',
            fontName='Helvetica-Bold',
            fontSize=11,
            textColor=colors.HexColor(self.branding.primary_color),
            spaceBefore=5,
            spaceAfter=5,
            leading=14,
        ))

        # Data Point
        self.styles.add(ParagraphStyle(
            name='DataPoint',
            fontName='Helvetica',
            fontSize=9,
            textColor=colors.HexColor('#7F8C8D'),
            leftIndent=10,
            spaceAfter=3,
            leading=12,
        ))

        # Footer
        self.styles.add(ParagraphStyle(
            name='Footer',
            fontName='Helvetica',
            fontSize=8,
            textColor=colors.HexColor('#95A5A6'),
            alignment=TA_CENTER,
        ))

    def _create_header_footer(
        self,
        canvas_obj: canvas.Canvas,
        doc,
        metadata: Dict[str, Any],
        is_cover: bool = False,
    ) -> None:
        """Create professional header and footer."""
        if is_cover:
            return

        canvas_obj.saveState()

        # Header line
        canvas_obj.setStrokeColor(colors.HexColor('#E0E0E0'))
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(50, self.height - 50, self.width - 50, self.height - 50)

        # Company name in header
        canvas_obj.setFillColor(colors.HexColor(self.branding.primary_color))
        canvas_obj.setFont('Helvetica-Bold', 9)
        canvas_obj.drawString(50, self.height - 40, self.branding.company_name)

        # Report title in header
        canvas_obj.setFillColor(colors.HexColor('#7F8C8D'))
        canvas_obj.setFont('Helvetica', 9)
        title = metadata.get('title', 'Report')[:40]
        canvas_obj.drawRightString(self.width - 50, self.height - 40, title)

        # Confidential badge
        if metadata.get('confidential', True):
            canvas_obj.setFillColor(colors.HexColor('#E74C3C'))
            canvas_obj.setFont('Helvetica-Bold', 7)
            canvas_obj.drawRightString(self.width - 50, self.height - 28, 'CONFIDENTIAL')

        # Footer line
        canvas_obj.line(50, 40, self.width - 50, 40)

        # Page number
        page_num = canvas_obj.getPageNumber()
        canvas_obj.setFillColor(colors.HexColor('#95A5A6'))
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.drawCentredString(self.width / 2, 25, f"Page {page_num}")

        # Date
        date_str = metadata.get('date', datetime.now().strftime('%Y-%m-%d'))
        canvas_obj.drawString(50, 25, f"Generated: {date_str}")

        # Website
        if self.branding.website:
            canvas_obj.drawRightString(self.width - 50, 25, self.branding.website)

        canvas_obj.restoreState()

    def _create_cover_page(self, data: EnterpriseReportData) -> List[Flowable]:
        """Create professional cover page."""
        elements = []

        elements.append(Spacer(1, 100))

        # Logo placeholder
        if self.branding.logo_path and Path(self.branding.logo_path).exists():
            try:
                logo = Image(self.branding.logo_path, width=150, height=60)
                logo.hAlign = 'CENTER'
                elements.append(logo)
                elements.append(Spacer(1, 40))
            except Exception as e:
                logger.warning("failed_to_load_logo", error=str(e))

        # Main title
        elements.append(Paragraph(data.report_title, self.styles['CoverTitle']))

        # Client name
        elements.append(Paragraph(
            f"Prepared for: <b>{data.client_name}</b>",
            self.styles['CoverSubtitle']
        ))

        # Period
        elements.append(Paragraph(
            f"Analysis Period: {data.report_period}",
            self.styles['CoverSubtitle']
        ))

        elements.append(Spacer(1, 60))

        # Key metrics preview
        if data.kpis:
            preview_data = [
                [kpi.title, kpi.format_value()]
                for kpi in data.kpis[:4]
            ]
            preview_table = Table(preview_data, colWidths=[200, 100])
            preview_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#7F8C8D')),
                ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor(self.branding.primary_color)),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(preview_table)

        elements.append(Spacer(1, 80))

        # Company info
        elements.append(Paragraph(
            self.branding.company_name,
            self.styles['CoverSubtitle']
        ))
        if self.branding.tagline:
            elements.append(Paragraph(
                self.branding.tagline,
                self.styles['Footer']
            ))

        # Generation date
        elements.append(Spacer(1, 20))
        elements.append(Paragraph(
            f"Report Generated: {data.generated_at.strftime('%B %d, %Y at %H:%M UTC')}",
            self.styles['Footer']
        ))

        elements.append(PageBreak())

        return elements

    def _create_executive_summary(self, data: EnterpriseReportData) -> List[Flowable]:
        """Create executive summary with KPI dashboard."""
        elements = []

        elements.append(SectionHeader("Executive Summary", self.branding,
                                      subtitle="Key Performance Indicators & Insights"))
        elements.append(Spacer(1, 20))

        # KPI Cards Grid (2x2 or 2x3)
        if data.kpis:
            kpi_cards = []
            row = []
            for i, kpi in enumerate(data.kpis[:6]):
                card = KPICardFlowable(kpi, self.branding, width=130, height=85)
                row.append(card)
                if len(row) == 3:
                    kpi_cards.append(row)
                    row = []
            if row:
                while len(row) < 3:
                    row.append(Spacer(130, 85))
                kpi_cards.append(row)

            kpi_table = Table(kpi_cards, colWidths=[140, 140, 140])
            kpi_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ]))
            elements.append(kpi_table)

        elements.append(Spacer(1, 25))

        # Quick Summary Text
        sentiment_emoji = "📈" if data.sentiment_score > 0.3 else "📉" if data.sentiment_score < -0.3 else "➡️"
        summary_text = f"""
        <b>Overall Assessment:</b> Analysis of <b>{data.total_reviews:,}</b> reviews across
        <b>{data.locations_analyzed}</b> locations reveals a <b>{data.overall_sentiment}</b> sentiment
        trend with a score of <b>{data.sentiment_score:.2f}</b>.

        {f"<br/><br/>This report includes {len(data.recommendations)} actionable recommendations prioritized by potential impact." if data.recommendations else ""}
        {f"<br/><br/><b>{len(data.anomalies)} anomalies</b> were detected requiring attention." if data.anomalies else ""}
        """
        elements.append(Paragraph(summary_text, self.styles['EnterpriseBody']))

        # Sentiment Gauge
        elements.append(Spacer(1, 15))
        gauge = GaugeChart(
            value=(data.sentiment_score + 1) * 50,  # Convert -1,1 to 0,100
            min_val=0,
            max_val=100,
            title="Sentiment Score",
            branding=self.branding,
            width=180,
            height=110,
        )
        elements.append(gauge)

        elements.append(PageBreak())

        return elements

    def _create_sentiment_analysis(self, data: EnterpriseReportData) -> List[Flowable]:
        """Create detailed sentiment analysis section."""
        elements = []

        elements.append(SectionHeader("Sentiment Analysis", self.branding,
                                      subtitle=f"Based on {data.total_reviews:,} reviews"))
        elements.append(Spacer(1, 15))

        # Sentiment Distribution Pie Chart
        drawing = Drawing(400, 200)
        pie = Pie()
        pie.x = 100
        pie.y = 30
        pie.width = 120
        pie.height = 120
        pie.data = [data.positive_count, data.neutral_count, data.negative_count]
        pie.labels = ['Positive', 'Neutral', 'Negative']
        pie.slices.strokeWidth = 0.5

        # Colors
        pie.slices[0].fillColor = colors.HexColor('#2ECC71')
        pie.slices[1].fillColor = colors.HexColor('#F1C40F')
        pie.slices[2].fillColor = colors.HexColor('#E74C3C')

        # Add percentages as labels
        total = data.positive_count + data.neutral_count + data.negative_count
        if total > 0:
            pie.slices[0].popout = 5
            for i, count in enumerate([data.positive_count, data.neutral_count, data.negative_count]):
                pct = (count / total) * 100
                pie.labels[i] = f'{pie.labels[i]}\n{pct:.1f}%'

        # Legend
        legend = Legend()
        legend.x = 280
        legend.y = 100
        legend.dx = 8
        legend.dy = 8
        legend.fontSize = 9
        legend.alignment = 'right'
        legend.colorNamePairs = [
            (colors.HexColor('#2ECC71'), f'Positive ({data.positive_count:,})'),
            (colors.HexColor('#F1C40F'), f'Neutral ({data.neutral_count:,})'),
            (colors.HexColor('#E74C3C'), f'Negative ({data.negative_count:,})'),
        ]

        drawing.add(pie)
        drawing.add(legend)

        # Title
        title = String(200, 180, 'Sentiment Distribution', fontName='Helvetica-Bold', fontSize=11, textAnchor='middle')
        drawing.add(title)

        elements.append(drawing)
        elements.append(Spacer(1, 20))

        # Sentiment Trend (if available)
        if data.sentiment_trend and len(data.sentiment_trend) > 1:
            elements.append(Paragraph("<b>Sentiment Trend Over Time</b>", self.styles['SubsectionTitle']))

            trend_drawing = Drawing(450, 180)
            chart = HorizontalLineChart()
            chart.x = 50
            chart.y = 40
            chart.width = 350
            chart.height = 120

            chart.data = [[v for _, v in data.sentiment_trend]]
            chart.categoryAxis.categoryNames = [d for d, _ in data.sentiment_trend]
            chart.categoryAxis.labels.angle = 45
            chart.categoryAxis.labels.fontSize = 7
            chart.categoryAxis.labels.boxAnchor = 'ne'

            chart.valueAxis.valueMin = -1
            chart.valueAxis.valueMax = 1
            chart.valueAxis.labels.fontSize = 8

            chart.lines[0].strokeColor = colors.HexColor(self.branding.primary_color)
            chart.lines[0].strokeWidth = 2

            trend_drawing.add(chart)
            elements.append(trend_drawing)

        elements.append(Spacer(1, 15))

        # Key Themes Table
        if data.key_themes:
            elements.append(Paragraph("<b>Key Themes Identified</b>", self.styles['SubsectionTitle']))

            theme_data = [['Theme', 'Frequency', 'Sentiment', 'Trend']]
            for theme in data.key_themes[:8]:
                trend_icon = "▲" if theme.get('trend', 'stable') == 'up' else "▼" if theme.get('trend') == 'down' else "─"
                theme_data.append([
                    theme.get('theme', 'N/A'),
                    str(theme.get('frequency', 0)),
                    theme.get('sentiment', 'N/A'),
                    trend_icon,
                ])

            theme_table = Table(theme_data, colWidths=[180, 80, 80, 50])
            theme_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(self.branding.primary_color)),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E0E0E0')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(theme_table)

        elements.append(PageBreak())

        return elements

    def _create_recommendations(self, data: EnterpriseReportData) -> List[Flowable]:
        """Create AI-powered recommendations section."""
        if not data.recommendations:
            return []

        elements = []

        elements.append(SectionHeader("AI-Powered Recommendations", self.branding,
                                      subtitle="Actionable insights prioritized by impact"))
        elements.append(Spacer(1, 15))

        priority_colors = {
            SeverityLevel.CRITICAL: '#E74C3C',
            SeverityLevel.HIGH: '#E67E22',
            SeverityLevel.MEDIUM: '#F1C40F',
            SeverityLevel.LOW: '#2ECC71',
            SeverityLevel.INFO: '#3498DB',
        }

        for i, rec in enumerate(data.recommendations[:6], 1):
            # Recommendation card
            rec_elements = []

            # Priority badge + Title
            priority_color = priority_colors.get(rec.priority, '#3498DB')
            title_text = f'<font color="{priority_color}">●</font> <b>{i}. {rec.title}</b>'
            rec_elements.append(Paragraph(title_text, self.styles['RecommendationTitle']))

            # Description
            rec_elements.append(Paragraph(rec.description, self.styles['EnterpriseBody']))

            # Impact/Effort badges
            badge_text = f'<font color="#7F8C8D">Impact: </font><b>{rec.impact}</b>  |  <font color="#7F8C8D">Effort: </font><b>{rec.effort}</b>  |  <font color="#7F8C8D">Category: </font><b>{rec.category}</b>'
            rec_elements.append(Paragraph(badge_text, self.styles['DataPoint']))

            # Data points
            if rec.data_points:
                for dp in rec.data_points[:3]:
                    rec_elements.append(Paragraph(f"• {dp}", self.styles['DataPoint']))

            # Action items
            if rec.action_items:
                rec_elements.append(Spacer(1, 5))
                rec_elements.append(Paragraph("<b>Recommended Actions:</b>", self.styles['DataPoint']))
                for action in rec.action_items[:3]:
                    rec_elements.append(Paragraph(f"  → {action}", self.styles['DataPoint']))

            rec_elements.append(Spacer(1, 15))

            # Keep together
            elements.append(KeepTogether(rec_elements))

        elements.append(PageBreak())

        return elements

    def _create_benchmarks(self, data: EnterpriseReportData) -> List[Flowable]:
        """Create industry benchmark comparison section."""
        if not data.benchmarks:
            return []

        elements = []

        elements.append(SectionHeader("Industry Benchmarks", self.branding,
                                      subtitle="How you compare to industry standards"))
        elements.append(Spacer(1, 20))

        for benchmark in data.benchmarks[:8]:
            elements.append(BenchmarkBar(benchmark, self.branding, width=450, height=45))
            elements.append(Spacer(1, 5))

        elements.append(Spacer(1, 20))

        # Summary stats
        above_avg = sum(1 for b in data.benchmarks if b.your_value >= b.industry_avg)
        total = len(data.benchmarks)

        summary = f"""
        <b>Benchmark Summary:</b> You are performing above industry average in <b>{above_avg}/{total}</b> metrics.
        Your average percentile ranking is <b>P{sum(b.percentile for b in data.benchmarks) // total}</b>.
        """
        elements.append(Paragraph(summary, self.styles['InsightBox']))

        elements.append(PageBreak())

        return elements

    def _create_competitor_analysis(self, data: EnterpriseReportData) -> List[Flowable]:
        """Create competitor comparison section."""
        if not data.competitors:
            return []

        elements = []

        elements.append(SectionHeader("Competitor Analysis", self.branding,
                                      subtitle="Competitive landscape overview"))
        elements.append(Spacer(1, 15))

        # Competitor comparison table
        comp_data = [['Competitor', 'Sentiment', 'Reviews', 'Rating', 'Trend']]

        # Add "You" as first row
        trend_icon = "▲" if data.sentiment_score > 0 else "▼" if data.sentiment_score < 0 else "─"
        comp_data.append([
            f"{data.client_name} (You)",
            f"{data.sentiment_score:.2f}",
            f"{data.total_reviews:,}",
            f"{sum(r.get('rating', 0) for r in data.location_data) / max(len(data.location_data), 1):.1f}",
            trend_icon,
        ])

        for comp in data.competitors[:5]:
            trend_icon = "▲" if comp.trend == TrendDirection.UP else "▼" if comp.trend == TrendDirection.DOWN else "─"
            comp_data.append([
                comp.name,
                f"{comp.sentiment_score:.2f}",
                f"{comp.review_count:,}",
                f"{comp.avg_rating:.1f}",
                trend_icon,
            ])

        comp_table = Table(comp_data, colWidths=[150, 80, 80, 60, 50])
        comp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(self.branding.primary_color)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#E8F6F3')),  # Highlight "You" row
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E0E0E0')),
            ('ROWBACKGROUNDS', (0, 2), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(comp_table)

        elements.append(Spacer(1, 20))

        # Competitor strengths/weaknesses (for top competitor)
        if data.competitors:
            top_comp = data.competitors[0]

            sw_data = []
            max_items = max(len(top_comp.strengths), len(top_comp.weaknesses))
            for i in range(min(max_items, 4)):
                strength = top_comp.strengths[i] if i < len(top_comp.strengths) else ""
                weakness = top_comp.weaknesses[i] if i < len(top_comp.weaknesses) else ""
                sw_data.append([f"✓ {strength}" if strength else "", f"✗ {weakness}" if weakness else ""])

            if sw_data:
                elements.append(Paragraph(f"<b>{top_comp.name} - SWOT Overview</b>", self.styles['SubsectionTitle']))

                sw_table = Table(
                    [['Strengths', 'Weaknesses']] + sw_data,
                    colWidths=[210, 210]
                )
                sw_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#2ECC71')),
                    ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#E74C3C')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E0E0E0')),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TEXTCOLOR', (0, 1), (0, -1), colors.HexColor('#27AE60')),
                    ('TEXTCOLOR', (1, 1), (1, -1), colors.HexColor('#C0392B')),
                ]))
                elements.append(sw_table)

        elements.append(PageBreak())

        return elements

    def _create_location_details(self, data: EnterpriseReportData) -> List[Flowable]:
        """Create detailed location analysis."""
        if not data.location_data:
            return []

        elements = []

        elements.append(SectionHeader("Location Analysis", self.branding,
                                      subtitle=f"Top performing and at-risk locations"))
        elements.append(Spacer(1, 15))

        # Sort locations by sentiment
        sorted_locations = sorted(data.location_data, key=lambda x: x.get('sentiment_score', 0), reverse=True)

        # Top 5 performing
        elements.append(Paragraph("<b>🌟 Top Performing Locations</b>", self.styles['SubsectionTitle']))

        top_data = [['Location', 'City', 'Sentiment', 'Reviews', 'Rating']]
        for loc in sorted_locations[:5]:
            top_data.append([
                loc.get('name', 'N/A')[:30],
                loc.get('city', 'N/A'),
                f"{loc.get('sentiment_score', 0):.2f}",
                str(loc.get('review_count', 0)),
                f"{loc.get('avg_rating', 0):.1f} ★",
            ])

        top_table = Table(top_data, colWidths=[150, 80, 70, 60, 60])
        top_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27AE60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E0E0E0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0FFF0')]),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(top_table)

        elements.append(Spacer(1, 20))

        # Bottom 5 (at risk)
        elements.append(Paragraph("<b>⚠️ Locations Requiring Attention</b>", self.styles['SubsectionTitle']))

        bottom_data = [['Location', 'City', 'Sentiment', 'Reviews', 'Rating']]
        for loc in sorted_locations[-5:]:
            bottom_data.append([
                loc.get('name', 'N/A')[:30],
                loc.get('city', 'N/A'),
                f"{loc.get('sentiment_score', 0):.2f}",
                str(loc.get('review_count', 0)),
                f"{loc.get('avg_rating', 0):.1f} ★",
            ])

        bottom_table = Table(bottom_data, colWidths=[150, 80, 70, 60, 60])
        bottom_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E74C3C')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E0E0E0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FFF0F0')]),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(bottom_table)

        elements.append(PageBreak())

        return elements

    def _create_anomalies_section(self, data: EnterpriseReportData) -> List[Flowable]:
        """Create anomaly alerts section."""
        if not data.anomalies:
            return []

        elements = []

        elements.append(SectionHeader("Anomaly Alerts", self.branding,
                                      subtitle=f"{len(data.anomalies)} anomalies detected"))
        elements.append(Spacer(1, 15))

        severity_colors = {
            'critical': '#E74C3C',
            'high': '#E67E22',
            'medium': '#F1C40F',
            'low': '#2ECC71',
        }

        for anomaly in data.anomalies[:10]:
            severity = anomaly.get('severity', 'medium').lower()
            color = severity_colors.get(severity, '#F1C40F')

            anomaly_text = f"""
            <font color="{color}"><b>● {anomaly.get('type', 'Anomaly').upper()}</b></font> - {anomaly.get('location', 'Unknown')}
            <br/>
            <font color="#7F8C8D">Detected: {anomaly.get('detected_at', 'N/A')} | Deviation: {anomaly.get('deviation', 0):.1f}%</font>
            <br/>
            {anomaly.get('description', '')}
            """
            elements.append(Paragraph(anomaly_text, self.styles['EnterpriseBody']))
            elements.append(Spacer(1, 10))

        elements.append(PageBreak())

        return elements

    def _create_appendix(self, data: EnterpriseReportData) -> List[Flowable]:
        """Create appendix with methodology and data sources."""
        elements = []

        elements.append(SectionHeader("Appendix", self.branding,
                                      subtitle="Methodology & Data Sources"))
        elements.append(Spacer(1, 15))

        # Methodology
        elements.append(Paragraph("<b>Methodology</b>", self.styles['SubsectionTitle']))
        methodology_text = f"""
        This report analyzes {data.total_reviews:,} reviews collected from {len(data.data_sources)} data sources
        across {data.locations_analyzed} locations. Sentiment analysis uses a combination of:
        <br/><br/>
        • <b>MiniLM embeddings</b> for semantic understanding (384-dimensional vectors)
        <br/>
        • <b>Isolation Forest</b> algorithm for anomaly detection
        <br/>
        • <b>Incremental statistics</b> using Welford's online algorithm
        <br/>
        • <b>Confidence level:</b> {data.confidence_level * 100:.0f}%
        """
        elements.append(Paragraph(methodology_text, self.styles['EnterpriseBody']))

        elements.append(Spacer(1, 20))

        # Data sources
        elements.append(Paragraph("<b>Data Sources</b>", self.styles['SubsectionTitle']))
        for source in data.data_sources:
            elements.append(Paragraph(f"• {source}", self.styles['DataPoint']))

        elements.append(Spacer(1, 20))

        # Disclaimer
        elements.append(Paragraph("<b>Disclaimer</b>", self.styles['SubsectionTitle']))
        disclaimer_text = """
        This report is provided for informational purposes only and should not be considered as
        investment advice. Past performance is not indicative of future results. The analysis
        is based on publicly available data and proprietary algorithms. All recommendations
        should be validated with additional research before implementation.
        """
        elements.append(Paragraph(disclaimer_text, self.styles['DataPoint']))

        return elements

    def generate_enterprise_report(
        self,
        data: EnterpriseReportData,
        output_path: str,
    ) -> Path:
        """
        Generate complete enterprise-grade PDF report.

        Args:
            data: Complete report data
            output_path: Path to save PDF

        Returns:
            Path to generated PDF
        """
        logger.info(
            "generating_enterprise_report",
            client=data.client_name,
            output_path=output_path,
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=self.page_size,
            rightMargin=50,
            leftMargin=50,
            topMargin=60,
            bottomMargin=50,
        )

        # Build story
        story = []

        # Cover page
        story.extend(self._create_cover_page(data))

        # Executive Summary
        story.extend(self._create_executive_summary(data))

        # Sentiment Analysis
        story.extend(self._create_sentiment_analysis(data))

        # AI Recommendations
        story.extend(self._create_recommendations(data))

        # Industry Benchmarks
        story.extend(self._create_benchmarks(data))

        # Competitor Analysis
        story.extend(self._create_competitor_analysis(data))

        # Location Details
        story.extend(self._create_location_details(data))

        # Anomaly Alerts
        story.extend(self._create_anomalies_section(data))

        # Appendix
        story.extend(self._create_appendix(data))

        # Build PDF with header/footer
        metadata = {
            'title': data.report_title,
            'date': data.generated_at.strftime('%Y-%m-%d'),
            'confidential': True,
        }

        doc.build(
            story,
            onFirstPage=lambda c, d: None,  # No header on cover
            onLaterPages=lambda c, d: self._create_header_footer(c, d, metadata),
        )

        logger.info("enterprise_report_generated", output_path=str(output_path))

        return output_path


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def generate_sample_enterprise_report(output_path: str = "/tmp/sample_enterprise_report.pdf") -> Path:
    """Generate a sample enterprise report with demo data."""

    # Sample KPIs
    kpis = [
        KPICard("Sentiment Score", 0.72, trend=TrendDirection.UP, trend_value=5.2,
                benchmark=0.65, severity=SeverityLevel.LOW),
        KPICard("Total Reviews", 15420, trend=TrendDirection.UP, trend_value=12.3,
                severity=SeverityLevel.INFO),
        KPICard("Avg Rating", 4.2, unit="★", trend=TrendDirection.STABLE,
                benchmark=4.0, severity=SeverityLevel.LOW),
        KPICard("Response Rate", 87.5, unit="%", trend=TrendDirection.UP, trend_value=3.1,
                benchmark=75.0, severity=SeverityLevel.LOW),
        KPICard("Anomalies", 3, trend=TrendDirection.DOWN, trend_value=-40.0,
                severity=SeverityLevel.MEDIUM),
        KPICard("NPS Score", 62, trend=TrendDirection.UP, trend_value=8.0,
                benchmark=50, severity=SeverityLevel.LOW),
    ]

    # Sample recommendations
    recommendations = [
        Recommendation(
            title="Improve Response Time to Negative Reviews",
            description="Analysis shows that locations with faster response times (<24h) have 23% higher sentiment recovery rates.",
            priority=SeverityLevel.HIGH,
            impact="High",
            effort="Low",
            category="Customer Service",
            data_points=[
                "Current avg response time: 48 hours",
                "Best performers respond within 4 hours",
                "67% of negative reviewers update their review after response",
            ],
            action_items=[
                "Set up automated alerts for new negative reviews",
                "Create response templates for common complaints",
                "Train staff on empathetic response techniques",
            ],
        ),
        Recommendation(
            title="Address Food Quality Concerns in NYC Locations",
            description="NYC locations show 15% lower sentiment scores related to food quality compared to other regions.",
            priority=SeverityLevel.MEDIUM,
            impact="High",
            effort="Medium",
            category="Operations",
            data_points=[
                "NYC food quality sentiment: 0.45 vs national avg 0.60",
                "Top complaints: temperature, portion size, freshness",
            ],
            action_items=[
                "Conduct quality audit at underperforming locations",
                "Review supply chain for NYC region",
            ],
        ),
    ]

    # Sample benchmarks
    benchmarks = [
        BenchmarkData("Overall Sentiment", 0.72, 0.65, 0.85, 68),
        BenchmarkData("Review Volume", 15420, 12000, 25000, 72),
        BenchmarkData("Average Rating", 4.2, 4.0, 4.7, 65),
        BenchmarkData("Response Rate", 87.5, 75.0, 95.0, 78),
        BenchmarkData("Customer Loyalty", 0.68, 0.55, 0.82, 71),
    ]

    # Sample competitors
    competitors = [
        CompetitorData(
            name="Competitor A",
            sentiment_score=0.68,
            review_count=18500,
            avg_rating=4.1,
            trend=TrendDirection.STABLE,
            strengths=["Strong brand recognition", "Wide menu variety"],
            weaknesses=["Inconsistent service", "Higher prices"],
        ),
        CompetitorData(
            name="Competitor B",
            sentiment_score=0.75,
            review_count=12000,
            avg_rating=4.3,
            trend=TrendDirection.UP,
            strengths=["Excellent customer service", "Modern locations"],
            weaknesses=["Limited locations", "Smaller portions"],
        ),
    ]

    # Sample location data
    location_data = [
        {"name": "Downtown Manhattan", "city": "New York", "sentiment_score": 0.82, "review_count": 450, "avg_rating": 4.5},
        {"name": "Chicago Loop", "city": "Chicago", "sentiment_score": 0.78, "review_count": 380, "avg_rating": 4.3},
        {"name": "Beverly Hills", "city": "Los Angeles", "sentiment_score": 0.76, "review_count": 290, "avg_rating": 4.4},
        {"name": "Back Bay", "city": "Boston", "sentiment_score": 0.74, "review_count": 210, "avg_rating": 4.2},
        {"name": "Financial District", "city": "San Francisco", "sentiment_score": 0.71, "review_count": 340, "avg_rating": 4.1},
        # At-risk locations
        {"name": "Times Square", "city": "New York", "sentiment_score": 0.42, "review_count": 520, "avg_rating": 3.2},
        {"name": "Airport Terminal", "city": "Chicago", "sentiment_score": 0.38, "review_count": 180, "avg_rating": 3.0},
        {"name": "Mall Location", "city": "Houston", "sentiment_score": 0.35, "review_count": 95, "avg_rating": 2.9},
    ]

    # Sample anomalies
    anomalies = [
        {
            "type": "Sentiment Drop",
            "location": "Times Square, NYC",
            "severity": "high",
            "detected_at": "2026-02-01",
            "deviation": -28.5,
            "description": "Sudden 28% drop in sentiment score over 48 hours. Correlates with staffing changes.",
        },
        {
            "type": "Volume Spike",
            "location": "Chicago Loop",
            "severity": "medium",
            "detected_at": "2026-02-02",
            "deviation": 45.0,
            "description": "Unusual 45% increase in review volume. Possible viral social media mention.",
        },
    ]

    # Create report data
    data = EnterpriseReportData(
        client_name="Acme Restaurant Group",
        report_title="Monthly Sentiment Analysis Report",
        report_period="January 2026",
        kpis=kpis,
        overall_sentiment="Positive",
        sentiment_score=0.72,
        positive_count=9852,
        negative_count=2310,
        neutral_count=3258,
        total_reviews=15420,
        sentiment_trend=[
            ("Week 1", 0.68), ("Week 2", 0.70), ("Week 3", 0.69), ("Week 4", 0.72),
        ],
        key_themes=[
            {"theme": "Food Quality", "frequency": 4521, "sentiment": "Positive", "trend": "up"},
            {"theme": "Service Speed", "frequency": 3210, "sentiment": "Mixed", "trend": "stable"},
            {"theme": "Cleanliness", "frequency": 2890, "sentiment": "Positive", "trend": "up"},
            {"theme": "Value for Money", "frequency": 2450, "sentiment": "Neutral", "trend": "down"},
            {"theme": "Atmosphere", "frequency": 1980, "sentiment": "Positive", "trend": "stable"},
        ],
        recommendations=recommendations,
        benchmarks=benchmarks,
        competitors=competitors,
        location_data=location_data,
        anomalies=anomalies,
        data_sources=["Google Maps", "Yelp", "TripAdvisor", "Internal Surveys"],
        locations_analyzed=127,
        confidence_level=0.95,
    )

    # Generate report
    branding = BrandingConfig(
        company_name="ReviewSignal.ai",
        tagline="Alternative Data Intelligence",
        website="reviewsignal.ai",
        primary_color="#1E3A5F",
        secondary_color="#4A90D9",
    )

    generator = EnterprisePDFGenerator(branding=branding)
    return generator.generate_enterprise_report(data, output_path)


if __name__ == "__main__":
    # Generate sample report for testing
    output = generate_sample_enterprise_report()
    print(f"Sample enterprise report generated: {output}")
