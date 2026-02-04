#!/usr/bin/env python3
"""
PDF Report Generator Module

This module provides comprehensive PDF generation capabilities for hedge fund reports,
including sentiment analysis reports, anomaly alerts, and monthly summaries.
Uses ReportLab library to create professional, styled PDF documents with tables,
charts, and custom layouts.

Features:
- Multiple report types (sentiment, anomaly, monthly summary)
- Custom styling with professional fonts and colors
- Table and chart generation
- Metadata support
- Flexible output formats
- Structured logging

Author: ReviewSignal Analytics Team
Version: 2.0
"""

import io
import structlog
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Union

# ReportLab imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
    Image,
    KeepTogether,
    Frame,
    PageTemplate,
)
from reportlab.platypus.flowables import Flowable, HRFlowable
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.legends import Legend

logger = structlog.get_logger(__name__)


class ReportType(Enum):
    """Enumeration of available report types."""
    SENTIMENT = "sentiment"
    ANOMALY = "anomaly"
    MONTHLY_SUMMARY = "monthly_summary"
    CUSTOM = "custom"


class OutputFormat(Enum):
    """Enumeration of output format options."""
    PDF = "pdf"
    LETTER = "letter"
    A4 = "a4"


class ChartType(Enum):
    """Enumeration of chart types supported in reports."""
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    HORIZONTAL_BAR = "horizontal_bar"


@dataclass
class ReportMetadata:
    """Metadata for report generation."""
    title: str
    author: str = "ReviewSignal Analytics"
    created_date: datetime = field(default_factory=datetime.now)
    client_name: Optional[str] = None
    report_period: Optional[str] = None
    version: str = "1.0"
    confidential: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary format."""
        return {
            "title": self.title,
            "author": self.author,
            "created_date": self.created_date.isoformat(),
            "client_name": self.client_name,
            "report_period": self.report_period,
            "version": self.version,
            "confidential": self.confidential,
        }


@dataclass
class ChartData:
    """Data structure for chart generation."""
    chart_type: ChartType
    title: str
    data: List[Tuple[str, float]]
    labels: Optional[List[str]] = None
    colors: Optional[List[str]] = None
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    width: float = 400
    height: float = 300

    def __post_init__(self):
        """Validate chart data after initialization."""
        if not self.data:
            raise ValueError("Chart data cannot be empty")
        if self.colors and len(self.colors) < len(self.data):
            logger.warning("Insufficient colors provided, using defaults")
            self.colors = None


@dataclass
class TableData:
    """Data structure for table generation."""
    headers: List[str]
    rows: List[List[Any]]
    title: Optional[str] = None
    column_widths: Optional[List[float]] = None
    style: str = "default"
    highlight_rows: Optional[List[int]] = None

    def __post_init__(self):
        """Validate table data after initialization."""
        if not self.headers:
            raise ValueError("Table headers cannot be empty")
        if self.rows and len(self.rows[0]) != len(self.headers):
            raise ValueError("Number of columns in rows must match headers")


@dataclass
class SentimentReportData:
    """Data structure for sentiment analysis reports."""
    overall_sentiment: str
    sentiment_score: float
    positive_count: int
    negative_count: int
    neutral_count: int
    total_reviews: int
    key_themes: List[Dict[str, Any]]
    sentiment_trend: List[Tuple[str, float]]
    top_positive_reviews: List[str]
    top_negative_reviews: List[str]
    recommendations: List[str]
    analysis_period: str
    data_sources: List[str]

    def get_sentiment_distribution(self) -> List[Tuple[str, int]]:
        """Get sentiment distribution data."""
        return [
            ("Positive", self.positive_count),
            ("Neutral", self.neutral_count),
            ("Negative", self.negative_count),
        ]


@dataclass
class AnomalyAlertData:
    """Data structure for anomaly detection alerts."""
    alert_id: str
    severity: str
    detected_at: datetime
    anomaly_type: str
    affected_metric: str
    baseline_value: float
    detected_value: float
    deviation_percent: float
    description: str
    potential_causes: List[str]
    recommended_actions: List[str]
    related_data: Optional[Dict[str, Any]] = None

    def get_severity_color(self) -> colors.Color:
        """Get color based on severity level."""
        severity_colors = {
            "critical": colors.red,
            "high": colors.orangered,
            "medium": colors.orange,
            "low": colors.yellow,
        }
        return severity_colors.get(self.severity.lower(), colors.grey)


class PDFReportGenerator:
    """
    Main class for generating professional PDF reports for hedge funds.

    This class provides comprehensive PDF generation capabilities with custom
    styling, tables, charts, and multiple report templates.
    """

    def __init__(
        self,
        output_format: OutputFormat = OutputFormat.LETTER,
        logo_path: Optional[str] = None,
    ):
        """
        Initialize PDF Report Generator.

        Args:
            output_format: Page format (LETTER or A4)
            logo_path: Optional path to company logo image
        """
        self.output_format = output_format
        self.logo_path = logo_path
        self.page_size = letter if output_format == OutputFormat.LETTER else A4
        self.width, self.height = self.page_size
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

        logger.info(
            "pdf_generator_initialized",
            output_format=output_format.value,
            page_size=self.page_size,
            has_logo=bool(logo_path),
        )

    def _setup_custom_styles(self) -> None:
        """
        Set up custom paragraph styles for reports.

        IMPORTANT: Uses 'ReportBodyText' instead of 'BodyText' to avoid conflicts
        with existing styles in the stylesheet.
        """
        # Custom Title Style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a2332'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            leading=30,
        ))

        # Custom Subtitle Style
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#4a5568'),
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Helvetica',
            leading=20,
        ))

        # Section Header Style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2d3748'),
            spaceAfter=12,
            spaceBefore=20,
            fontName='Helvetica-Bold',
            leading=18,
            borderWidth=0,
            borderColor=colors.HexColor('#cbd5e0'),
            borderPadding=5,
            backColor=colors.HexColor('#f7fafc'),
        ))

        # Custom Body Text Style (renamed to avoid conflicts)
        self.styles.add(ParagraphStyle(
            name='ReportBodyText',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#2d3748'),
            spaceAfter=12,
            alignment=TA_JUSTIFY,
            fontName='Helvetica',
            leading=16,
        ))

        # Insight Box Style
        self.styles.add(ParagraphStyle(
            name='InsightBox',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#2c5282'),
            spaceAfter=10,
            spaceBefore=10,
            leftIndent=20,
            rightIndent=20,
            fontName='Helvetica-Oblique',
            backColor=colors.HexColor('#ebf8ff'),
            borderWidth=1,
            borderColor=colors.HexColor('#4299e1'),
            borderPadding=10,
            leading=14,
        ))

        logger.debug("custom_styles_configured", style_count=5)

    def _create_header_footer(
        self,
        canvas_obj: canvas.Canvas,
        doc: SimpleDocTemplate,
        metadata: ReportMetadata,
    ) -> None:
        """
        Create header and footer for each page.

        Args:
            canvas_obj: ReportLab canvas object
            doc: Document template
            metadata: Report metadata
        """
        canvas_obj.saveState()

        # Header
        if self.logo_path and Path(self.logo_path).exists():
            try:
                canvas_obj.drawImage(
                    self.logo_path,
                    40,
                    self.height - 60,
                    width=80,
                    height=40,
                    preserveAspectRatio=True,
                )
            except Exception as e:
                logger.warning("failed_to_load_logo", error=str(e))

        # Confidentiality notice in header
        if metadata.confidential:
            canvas_obj.setFont('Helvetica-Bold', 8)
            canvas_obj.setFillColor(colors.red)
            canvas_obj.drawRightString(
                self.width - 40,
                self.height - 40,
                "CONFIDENTIAL"
            )

        # Footer
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(colors.grey)

        # Page number
        page_num = canvas_obj.getPageNumber()
        canvas_obj.drawString(
            40,
            30,
            f"Page {page_num}"
        )

        # Date and company info
        footer_text = f"{metadata.author} | Generated: {metadata.created_date.strftime('%Y-%m-%d %H:%M')}"
        canvas_obj.drawRightString(
            self.width - 40,
            30,
            footer_text
        )

        # Draw header/footer lines
        canvas_obj.setStrokeColor(colors.HexColor('#cbd5e0'))
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(40, self.height - 70, self.width - 40, self.height - 70)
        canvas_obj.line(40, 50, self.width - 40, 50)

        canvas_obj.restoreState()

    def _create_chart(self, chart_data: ChartData) -> Drawing:
        """
        Create a chart based on provided data.

        Args:
            chart_data: Chart configuration and data

        Returns:
            ReportLab Drawing object containing the chart
        """
        drawing = Drawing(chart_data.width, chart_data.height)

        try:
            if chart_data.chart_type == ChartType.BAR:
                chart = self._create_bar_chart(chart_data, drawing)
            elif chart_data.chart_type == ChartType.LINE:
                chart = self._create_line_chart(chart_data, drawing)
            elif chart_data.chart_type == ChartType.PIE:
                chart = self._create_pie_chart(chart_data, drawing)
            else:
                logger.warning("unsupported_chart_type", chart_type=chart_data.chart_type)
                return drawing

            drawing.add(chart)
            logger.debug("chart_created", chart_type=chart_data.chart_type.value)

        except Exception as e:
            logger.error("chart_creation_failed", error=str(e), chart_type=chart_data.chart_type)

        return drawing

    def _create_bar_chart(self, chart_data: ChartData, drawing: Drawing) -> VerticalBarChart:
        """Create a vertical bar chart."""
        chart = VerticalBarChart()
        chart.x = 50
        chart.y = 50
        chart.height = chart_data.height - 100
        chart.width = chart_data.width - 100

        # Prepare data
        labels = [item[0] for item in chart_data.data]
        values = [[item[1] for item in chart_data.data]]

        chart.data = values
        chart.categoryAxis.categoryNames = labels
        chart.categoryAxis.labels.boxAnchor = 'ne'
        chart.categoryAxis.labels.angle = 45
        chart.categoryAxis.labels.fontSize = 8

        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = max([v for _, v in chart_data.data]) * 1.2
        chart.valueAxis.labels.fontSize = 8

        # Set colors
        if chart_data.colors:
            chart.bars[0].fillColor = colors.HexColor(chart_data.colors[0])
        else:
            chart.bars[0].fillColor = colors.HexColor('#4299e1')

        # Add title
        title = String(
            chart_data.width / 2,
            chart_data.height - 30,
            chart_data.title,
            textAnchor='middle',
            fontSize=12,
            fontName='Helvetica-Bold',
        )
        drawing.add(title)

        return chart

    def _create_line_chart(self, chart_data: ChartData, drawing: Drawing) -> HorizontalLineChart:
        """Create a line chart."""
        chart = HorizontalLineChart()
        chart.x = 50
        chart.y = 50
        chart.height = chart_data.height - 100
        chart.width = chart_data.width - 100

        # Prepare data
        values = [[item[1] for item in chart_data.data]]
        chart.data = values

        chart.lines[0].strokeColor = colors.HexColor('#4299e1')
        chart.lines[0].strokeWidth = 2
        chart.lines[0].symbol = None

        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = max([v for _, v in chart_data.data]) * 1.2
        chart.valueAxis.labels.fontSize = 8

        chart.categoryAxis.labels.fontSize = 8
        chart.categoryAxis.categoryNames = [item[0] for item in chart_data.data]

        # Add title
        title = String(
            chart_data.width / 2,
            chart_data.height - 30,
            chart_data.title,
            textAnchor='middle',
            fontSize=12,
            fontName='Helvetica-Bold',
        )
        drawing.add(title)

        return chart

    def _create_pie_chart(self, chart_data: ChartData, drawing: Drawing) -> Pie:
        """Create a pie chart."""
        pie = Pie()
        pie.x = chart_data.width / 2 - 100
        pie.y = chart_data.height / 2 - 100
        pie.width = 200
        pie.height = 200

        # Prepare data
        pie.data = [item[1] for item in chart_data.data]
        pie.labels = [item[0] for item in chart_data.data]

        # Set colors
        if chart_data.colors:
            pie.slices.strokeColor = colors.white
            pie.slices.strokeWidth = 1
            for i, color in enumerate(chart_data.colors[:len(pie.data)]):
                pie.slices[i].fillColor = colors.HexColor(color)
        else:
            default_colors = ['#4299e1', '#48bb78', '#ed8936', '#f56565', '#9f7aea']
            for i, color in enumerate(default_colors[:len(pie.data)]):
                pie.slices[i].fillColor = colors.HexColor(color)

        # Add legend
        legend = Legend()
        legend.x = chart_data.width - 120
        legend.y = chart_data.height / 2
        legend.columnMaximum = 10
        legend.alignment = 'right'
        legend.fontSize = 8
        legend.colorNamePairs = [(pie.slices[i].fillColor, pie.labels[i]) for i in range(len(pie.data))]
        drawing.add(legend)

        # Add title
        title = String(
            chart_data.width / 2,
            chart_data.height - 30,
            chart_data.title,
            textAnchor='middle',
            fontSize=12,
            fontName='Helvetica-Bold',
        )
        drawing.add(title)

        return pie

    def _create_table(self, table_data: TableData) -> Table:
        """
        Create a styled table.

        Args:
            table_data: Table configuration and data

        Returns:
            ReportLab Table object
        """
        # Prepare table data with headers
        data = [table_data.headers] + table_data.rows

        # Create table
        table = Table(data, colWidths=table_data.column_widths)

        # Define table styles
        style = [
            # Header styling
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d3748')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),

            # Body styling
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#2d3748')),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
            ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#2d3748')),

            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
        ]

        # Highlight specific rows if specified
        if table_data.highlight_rows:
            for row_idx in table_data.highlight_rows:
                style.append(('BACKGROUND', (0, row_idx + 1), (-1, row_idx + 1), colors.HexColor('#fff5f5')))

        table.setStyle(TableStyle(style))

        logger.debug(
            "table_created",
            rows=len(table_data.rows),
            columns=len(table_data.headers),
        )

        return table

    def generate_sentiment_report(
        self,
        data: SentimentReportData,
        output_path: str,
        metadata: Optional[ReportMetadata] = None,
    ) -> Path:
        """
        Generate a comprehensive sentiment analysis report.

        Args:
            data: Sentiment report data
            output_path: Path to save the generated PDF
            metadata: Optional report metadata

        Returns:
            Path to generated PDF file
        """
        if metadata is None:
            metadata = ReportMetadata(
                title="Sentiment Analysis Report",
                report_period=data.analysis_period,
            )

        logger.info(
            "generating_sentiment_report",
            output_path=output_path,
            total_reviews=data.total_reviews,
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=self.page_size,
            rightMargin=72,
            leftMargin=72,
            topMargin=100,
            bottomMargin=72,
        )

        story = []

        # Title and metadata
        story.append(Paragraph(metadata.title, self.styles['CustomTitle']))
        story.append(Paragraph(f"Analysis Period: {data.analysis_period}", self.styles['CustomSubtitle']))
        story.append(Spacer(1, 20))

        # Executive Summary
        story.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
        summary_text = f"""
        This report presents a comprehensive sentiment analysis of {data.total_reviews} reviews
        across {len(data.data_sources)} data sources. The overall sentiment is classified as
        <b>{data.overall_sentiment}</b> with a sentiment score of <b>{data.sentiment_score:.2f}</b>.
        The analysis reveals {data.positive_count} positive, {data.neutral_count} neutral,
        and {data.negative_count} negative reviews.
        """
        story.append(Paragraph(summary_text, self.styles['ReportBodyText']))
        story.append(Spacer(1, 20))

        # Sentiment Distribution Chart
        story.append(Paragraph("Sentiment Distribution", self.styles['SectionHeader']))
        sentiment_chart = ChartData(
            chart_type=ChartType.PIE,
            title="Review Sentiment Breakdown",
            data=data.get_sentiment_distribution(),
            colors=['#48bb78', '#ecc94b', '#f56565'],
        )
        story.append(self._create_chart(sentiment_chart))
        story.append(Spacer(1, 20))

        # Sentiment Trend
        if data.sentiment_trend:
            story.append(Paragraph("Sentiment Trend Over Time", self.styles['SectionHeader']))
            trend_chart = ChartData(
                chart_type=ChartType.LINE,
                title="Sentiment Score Progression",
                data=data.sentiment_trend,
            )
            story.append(self._create_chart(trend_chart))
            story.append(Spacer(1, 20))

        # Key Themes
        story.append(Paragraph("Key Themes Identified", self.styles['SectionHeader']))
        if data.key_themes:
            theme_rows = [
                [theme.get('theme', 'N/A'), str(theme.get('frequency', 0)), theme.get('sentiment', 'N/A')]
                for theme in data.key_themes
            ]
            theme_table = TableData(
                headers=["Theme", "Frequency", "Sentiment"],
                rows=theme_rows,
            )
            story.append(self._create_table(theme_table))
        story.append(Spacer(1, 20))

        # Top Positive Reviews
        story.append(Paragraph("Top Positive Insights", self.styles['SectionHeader']))
        for i, review in enumerate(data.top_positive_reviews[:5], 1):
            story.append(Paragraph(f"{i}. {review}", self.styles['ReportBodyText']))
        story.append(Spacer(1, 20))

        # Top Negative Reviews
        story.append(Paragraph("Areas of Concern", self.styles['SectionHeader']))
        for i, review in enumerate(data.top_negative_reviews[:5], 1):
            story.append(Paragraph(f"{i}. {review}", self.styles['ReportBodyText']))
        story.append(Spacer(1, 20))

        # Recommendations
        story.append(Paragraph("Strategic Recommendations", self.styles['SectionHeader']))
        for i, rec in enumerate(data.recommendations, 1):
            story.append(Paragraph(f"{i}. {rec}", self.styles['InsightBox']))

        # Build PDF
        doc.build(
            story,
            onFirstPage=lambda c, d: self._create_header_footer(c, d, metadata),
            onLaterPages=lambda c, d: self._create_header_footer(c, d, metadata),
        )

        logger.info("sentiment_report_generated", output_path=str(output_path))
        return output_path

    def generate_anomaly_alert(
        self,
        data: AnomalyAlertData,
        output_path: str,
    ) -> Path:
        """
        Generate an anomaly detection alert report.

        Args:
            data: Anomaly alert data
            output_path: Path to save the generated PDF

        Returns:
            Path to generated PDF file
        """
        metadata = ReportMetadata(
            title=f"Anomaly Alert: {data.alert_id}",
            report_period=data.detected_at.strftime('%Y-%m-%d %H:%M'),
        )

        logger.info(
            "generating_anomaly_alert",
            alert_id=data.alert_id,
            severity=data.severity,
            output_path=output_path,
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=self.page_size,
            rightMargin=72,
            leftMargin=72,
            topMargin=100,
            bottomMargin=72,
        )

        story = []

        # Title
        story.append(Paragraph(f"ANOMALY ALERT: {data.alert_id}", self.styles['CustomTitle']))
        severity_color = data.get_severity_color()
        severity_style = ParagraphStyle(
            name='SeverityStyle',
            parent=self.styles['CustomSubtitle'],
            textColor=severity_color,
        )
        story.append(Paragraph(f"Severity: {data.severity.upper()}", severity_style))
        story.append(Spacer(1, 30))

        # Alert Summary
        story.append(Paragraph("Alert Summary", self.styles['SectionHeader']))
        summary_data = TableData(
            headers=["Property", "Value"],
            rows=[
                ["Alert ID", data.alert_id],
                ["Detected At", data.detected_at.strftime('%Y-%m-%d %H:%M:%S')],
                ["Anomaly Type", data.anomaly_type],
                ["Affected Metric", data.affected_metric],
                ["Severity", data.severity.upper()],
            ],
        )
        story.append(self._create_table(summary_data))
        story.append(Spacer(1, 20))

        # Deviation Details
        story.append(Paragraph("Deviation Analysis", self.styles['SectionHeader']))
        deviation_text = f"""
        The detected value of <b>{data.detected_value:.2f}</b> deviates from the baseline value of
        <b>{data.baseline_value:.2f}</b> by <b>{data.deviation_percent:.1f}%</b>.
        This significant deviation triggered an automatic alert in our monitoring system.
        """
        story.append(Paragraph(deviation_text, self.styles['ReportBodyText']))
        story.append(Spacer(1, 20))

        # Description
        story.append(Paragraph("Detailed Description", self.styles['SectionHeader']))
        story.append(Paragraph(data.description, self.styles['ReportBodyText']))
        story.append(Spacer(1, 20))

        # Potential Causes
        story.append(Paragraph("Potential Root Causes", self.styles['SectionHeader']))
        for i, cause in enumerate(data.potential_causes, 1):
            story.append(Paragraph(f"{i}. {cause}", self.styles['ReportBodyText']))
        story.append(Spacer(1, 20))

        # Recommended Actions
        story.append(Paragraph("Recommended Actions", self.styles['SectionHeader']))
        for i, action in enumerate(data.recommended_actions, 1):
            story.append(Paragraph(f"{i}. {action}", self.styles['InsightBox']))
        story.append(Spacer(1, 20))

        # Related Data
        if data.related_data:
            story.append(Paragraph("Related Metrics", self.styles['SectionHeader']))
            related_rows = [[k, str(v)] for k, v in data.related_data.items()]
            related_table = TableData(
                headers=["Metric", "Value"],
                rows=related_rows,
            )
            story.append(self._create_table(related_table))

        doc.build(
            story,
            onFirstPage=lambda c, d: self._create_header_footer(c, d, metadata),
            onLaterPages=lambda c, d: self._create_header_footer(c, d, metadata),
        )

        logger.info("anomaly_alert_generated", output_path=str(output_path))
        return output_path

    def generate_monthly_summary(
        self,
        client_name: str,
        month: int,
        year: int,
        metrics: Dict[str, Any],
        output_path: str,
    ) -> Path:
        """
        Generate a monthly summary report for a client.

        Args:
            client_name: Name of the client
            month: Month number (1-12)
            year: Year
            metrics: Dictionary of metrics to include
            output_path: Path to save the generated PDF

        Returns:
            Path to generated PDF file
        """
        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        period = f"{month_names[month - 1]} {year}"

        metadata = ReportMetadata(
            title="Monthly Performance Summary",
            client_name=client_name,
            report_period=period,
        )

        logger.info(
            "generating_monthly_summary",
            client_name=client_name,
            period=period,
            output_path=output_path,
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=self.page_size,
            rightMargin=72,
            leftMargin=72,
            topMargin=100,
            bottomMargin=72,
        )

        story = []

        # Title
        story.append(Paragraph(f"Monthly Summary Report", self.styles['CustomTitle']))
        story.append(Paragraph(f"{client_name}", self.styles['CustomSubtitle']))
        story.append(Paragraph(f"{period}", self.styles['CustomSubtitle']))
        story.append(Spacer(1, 30))

        # Executive Overview
        story.append(Paragraph("Executive Overview", self.styles['SectionHeader']))
        overview_text = f"""
        This report provides a comprehensive overview of performance metrics for {client_name}
        during {period}. The analysis includes key performance indicators, trend analysis,
        and actionable insights for strategic decision-making.
        """
        story.append(Paragraph(overview_text, self.styles['ReportBodyText']))
        story.append(Spacer(1, 20))

        # Key Metrics Summary
        story.append(Paragraph("Key Metrics Summary", self.styles['SectionHeader']))
        metric_rows = []
        for metric_name, metric_value in metrics.items():
            if isinstance(metric_value, (int, float)):
                formatted_value = f"{metric_value:,.2f}" if isinstance(metric_value, float) else f"{metric_value:,}"
            else:
                formatted_value = str(metric_value)
            metric_rows.append([metric_name.replace('_', ' ').title(), formatted_value])

        metrics_table = TableData(
            headers=["Metric", "Value"],
            rows=metric_rows,
        )
        story.append(self._create_table(metrics_table))
        story.append(Spacer(1, 20))

        # Performance Visualization
        if any(isinstance(v, (int, float)) for v in metrics.values()):
            story.append(Paragraph("Performance Metrics Visualization", self.styles['SectionHeader']))
            numeric_metrics = [(k.replace('_', ' ').title(), float(v))
                             for k, v in metrics.items()
                             if isinstance(v, (int, float))][:8]  # Limit to 8 for readability

            if numeric_metrics:
                metrics_chart = ChartData(
                    chart_type=ChartType.BAR,
                    title="Key Performance Indicators",
                    data=numeric_metrics,
                )
                story.append(self._create_chart(metrics_chart))
                story.append(Spacer(1, 20))

        # Insights and Recommendations
        story.append(Paragraph("Key Insights", self.styles['SectionHeader']))
        insights = [
            "Performance metrics show consistent improvement across key indicators.",
            "Client engagement levels remain strong with positive trend indicators.",
            "Continued monitoring recommended for sustained performance optimization.",
        ]
        for i, insight in enumerate(insights, 1):
            story.append(Paragraph(f"{i}. {insight}", self.styles['InsightBox']))

        doc.build(
            story,
            onFirstPage=lambda c, d: self._create_header_footer(c, d, metadata),
            onLaterPages=lambda c, d: self._create_header_footer(c, d, metadata),
        )

        logger.info("monthly_summary_generated", output_path=str(output_path))
        return output_path


def generate_quick_sentiment_report(
    sentiment_score: float,
    positive_count: int,
    negative_count: int,
    neutral_count: int,
    output_path: str,
) -> Path:
    """
    Convenience function to quickly generate a basic sentiment report.

    Args:
        sentiment_score: Overall sentiment score (-1 to 1)
        positive_count: Number of positive reviews
        negative_count: Number of negative reviews
        neutral_count: Number of neutral reviews
        output_path: Path to save the PDF

    Returns:
        Path to generated PDF file
    """
    total_reviews = positive_count + negative_count + neutral_count

    # Determine overall sentiment
    if sentiment_score > 0.3:
        overall_sentiment = "Positive"
    elif sentiment_score < -0.3:
        overall_sentiment = "Negative"
    else:
        overall_sentiment = "Neutral"

    # Create minimal report data
    data = SentimentReportData(
        overall_sentiment=overall_sentiment,
        sentiment_score=sentiment_score,
        positive_count=positive_count,
        negative_count=negative_count,
        neutral_count=neutral_count,
        total_reviews=total_reviews,
        key_themes=[],
        sentiment_trend=[],
        top_positive_reviews=["Positive feedback noted"],
        top_negative_reviews=["Areas for improvement identified"],
        recommendations=["Continue monitoring sentiment trends", "Address negative feedback promptly"],
        analysis_period=datetime.now().strftime('%Y-%m-%d'),
        data_sources=["Quick Report"],
    )

    generator = PDFReportGenerator()
    return generator.generate_sentiment_report(data, output_path)


if __name__ == "__main__":
    # Example usage and testing
    logger.info("pdf_generator_module_loaded")

    # Test basic initialization
    generator = PDFReportGenerator(output_format=OutputFormat.LETTER)
    logger.info("test_generator_initialized")

    print("PDF Generator module loaded successfully!")
    print("Available classes:")
    print("  - ReportType, OutputFormat, ChartType (Enums)")
    print("  - ReportMetadata, ChartData, TableData (Data classes)")
    print("  - SentimentReportData, AnomalyAlertData (Report data)")
    print("  - PDFReportGenerator (Main generator class)")
    print("\nMain methods:")
    print("  - generate_sentiment_report()")
    print("  - generate_anomaly_alert()")
    print("  - generate_monthly_summary()")
    print("\nConvenience functions:")
    print("  - generate_quick_sentiment_report()")
