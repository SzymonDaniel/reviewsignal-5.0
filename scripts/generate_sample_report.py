#!/usr/bin/env python3
"""
Standalone Sample PDF Report Generator for ReviewSignal.
Generates a demo enterprise report using only reportlab (no structlog).
"""
import sys, os, math
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Union

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, PageBreak, KeepTogether, Flowable)
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.legends import Legend

class SeverityLevel(Enum):
    CRITICAL="critical"; HIGH="high"; MEDIUM="medium"; LOW="low"; INFO="info"

class TrendDirection(Enum):
    UP="up"; DOWN="down"; STABLE="stable"

@dataclass
class BrandingConfig:
    company_name: str = "ReviewSignal.ai"
    tagline: Optional[str] = "Alternative Data Intelligence"
    website: Optional[str] = "reviewsignal.ai"
    primary_color: str = "#1E3A5F"
    secondary_color: str = "#4A90D9"

@dataclass
class KPICard:
    title: str; value: Union[str,int,float]; unit: str = ""
    trend: Optional[TrendDirection] = None; trend_value: Optional[float] = None
    benchmark: Optional[float] = None; severity: SeverityLevel = SeverityLevel.INFO
    def format_value(self):
        if isinstance(self.value, float):
            return f"{self.value:.1f}%" if self.unit == "%" else f"{self.value:,.2f}"
        if isinstance(self.value, int): return f"{self.value:,}"
        return str(self.value)

@dataclass
class Recommendation:
    title: str; description: str; priority: SeverityLevel = SeverityLevel.MEDIUM
    impact: str = "Medium"; effort: str = "Medium"; category: str = "General"
    data_points: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)

@dataclass
class BenchmarkData:
    metric_name: str; your_value: float; industry_avg: float
    industry_best: float; percentile: int

@dataclass
class CompetitorData:
    name: str; sentiment_score: float; review_count: int; avg_rating: float
    trend: TrendDirection
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)

class KPICardFlowable(Flowable):
    def __init__(self, kpi, branding, width=120, height=80):
        Flowable.__init__(self); self.kpi=kpi; self.branding=branding; self.width=width; self.height=height
    def draw(self):
        c=self.canv
        c.setFillColor(colors.white); c.setStrokeColor(colors.HexColor("#E0E0E0"))
        c.roundRect(0,0,self.width,self.height,8,fill=1,stroke=1)
        sc={SeverityLevel.CRITICAL:"#E74C3C",SeverityLevel.HIGH:"#E67E22",SeverityLevel.MEDIUM:"#F1C40F",SeverityLevel.LOW:"#2ECC71",SeverityLevel.INFO:"#3498DB"}
        c.setFillColor(colors.HexColor(sc.get(self.kpi.severity,"#3498DB")))
        c.rect(0,self.height-6,self.width,6,fill=1,stroke=0)
        c.setFillColor(colors.HexColor("#7F8C8D")); c.setFont("Helvetica",8)
        c.drawString(10,self.height-22,self.kpi.title[:20])
        c.setFillColor(colors.HexColor(self.branding.primary_color)); c.setFont("Helvetica-Bold",18)
        v=self.kpi.format_value(); c.drawString(10,self.height-48,v)
        if self.kpi.benchmark is not None:
            c.setFillColor(colors.HexColor("#95A5A6")); c.setFont("Helvetica",7)
            c.drawString(10,12,f"Industry Avg: {self.kpi.benchmark:.1f}")

class SectionHeaderFlowable(Flowable):
    def __init__(self, title, branding, width=500, subtitle=None):
        Flowable.__init__(self); self.title=title; self.branding=branding
        self.width=width; self.subtitle=subtitle; self.height=40 if subtitle else 30
    def draw(self):
        c=self.canv
        c.setFillColor(colors.HexColor(self.branding.primary_color))
        c.rect(0,0,4,self.height,fill=1,stroke=0)
        c.setFont("Helvetica-Bold",14); c.drawString(15,self.height-18,self.title.upper())
        if self.subtitle:
            c.setFillColor(colors.HexColor("#7F8C8D")); c.setFont("Helvetica",9)
            c.drawString(15,8,self.subtitle)
        c.setStrokeColor(colors.HexColor("#E0E0E0")); c.setLineWidth(0.5)
        c.line(0,0,self.width,0)

class BenchmarkBarFlowable(Flowable):
    def __init__(self, bm, branding, width=400, height=50):
        Flowable.__init__(self); self.bm=bm; self.branding=branding; self.width=width; self.height=height
    def draw(self):
        c=self.canv; bh=12; by=self.height/2-bh/2; lw=120; bw=self.width-lw-80
        yv=float(self.bm.your_value); ia=float(self.bm.industry_avg); ib=float(self.bm.industry_best)
        c.setFillColor(colors.HexColor("#2C3E50")); c.setFont("Helvetica",9)
        c.drawString(0,by+2,self.bm.metric_name[:25])
        c.setFillColor(colors.HexColor("#ECF0F1")); c.roundRect(lw,by,bw,bh,3,fill=1,stroke=0)
        if ia>0 and ib>0:
            ax=lw+(ia/ib)*bw; c.setStrokeColor(colors.HexColor("#95A5A6")); c.setLineWidth(2)
            c.line(ax,by-3,ax,by+bh+3)
        yr=min(yv/ib,1.0) if ib>0 else 0; yw=yr*bw
        bc="#2ECC71" if yv>=ia else "#E74C3C"
        c.setFillColor(colors.HexColor(bc)); c.roundRect(lw,by,yw,bh,3,fill=1,stroke=0)
        c.setFillColor(colors.HexColor("#2C3E50")); c.setFont("Helvetica-Bold",9)
        c.drawString(lw+bw+10,by+2,f"{yv:.1f}")
        c.setFillColor(colors.HexColor(self.branding.secondary_color))
        c.roundRect(self.width-45,by-2,40,bh+4,3,fill=1,stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold",8)
        c.drawCentredString(self.width-25,by+2,f"P{self.bm.percentile}")

class GaugeChart(Flowable):
    def __init__(self, value, branding=None, width=200, height=150, title=""):
        Flowable.__init__(self); self.value=value; self.branding=branding or BrandingConfig()
        self.width=width; self.height=height; self.title=title
    def draw(self):
        c=self.canv; cx=self.width/2; cy=self.height*0.4; r=min(self.width,self.height)*0.35
        for sp,ep,col in [(0,30,"#E74C3C"),(30,60,"#F1C40F"),(60,100,"#2ECC71")]:
            c.setLineWidth(12)
            for i in range(int(180-sp/100*180),int(180-ep/100*180),-1):
                a=math.radians(i); x=cx+r*math.cos(a); y=cy+r*math.sin(a)
                c.setStrokeColor(colors.HexColor(col)); c.circle(x,y,1,fill=1,stroke=0)
        n=(self.value-0)/(100-0); na=math.radians(180-n*180); nl=r*0.8
        c.setStrokeColor(colors.HexColor(self.branding.primary_color))
        c.setFillColor(colors.HexColor(self.branding.primary_color)); c.setLineWidth(2)
        c.line(cx,cy,cx+nl*math.cos(na),cy+nl*math.sin(na)); c.circle(cx,cy,5,fill=1,stroke=0)
        c.setFont("Helvetica-Bold",16); c.drawCentredString(cx,cy-25,f"{self.value:.1f}")
        if self.title:
            c.setFillColor(colors.HexColor("#7F8C8D")); c.setFont("Helvetica",9)
            c.drawCentredString(cx,self.height-15,self.title)

class SampleReportGenerator:
    def __init__(self, branding=None):
        self.branding=branding or BrandingConfig()
        self.page_size=letter; self.width,self.height=self.page_size
        self.styles=getSampleStyleSheet(); self._setup()

    def _setup(self):
        s=self.styles; b=self.branding
        s.add(ParagraphStyle(name='CT',fontName='Helvetica-Bold',fontSize=32,textColor=colors.HexColor(b.primary_color),alignment=TA_CENTER,spaceAfter=20,leading=40))
        s.add(ParagraphStyle(name='CS',fontName='Helvetica',fontSize=16,textColor=colors.HexColor('#7F8C8D'),alignment=TA_CENTER,spaceAfter=10,leading=22))
        s.add(ParagraphStyle(name='SS',fontName='Helvetica-Bold',fontSize=12,textColor=colors.HexColor('#2C3E50'),spaceBefore=15,spaceAfter=8,leading=16))
        s.add(ParagraphStyle(name='EB',fontName='Helvetica',fontSize=10,textColor=colors.HexColor('#2C3E50'),alignment=TA_JUSTIFY,spaceAfter=10,leading=14))
        s.add(ParagraphStyle(name='IB',fontName='Helvetica-Oblique',fontSize=10,textColor=colors.HexColor(b.secondary_color),leftIndent=20,rightIndent=20,spaceBefore=10,spaceAfter=10,leading=14,backColor=colors.HexColor('#F8F9FA'),borderWidth=1,borderColor=colors.HexColor(b.secondary_color),borderPadding=10))
        s.add(ParagraphStyle(name='RT',fontName='Helvetica-Bold',fontSize=11,textColor=colors.HexColor(b.primary_color),spaceBefore=5,spaceAfter=5,leading=14))
        s.add(ParagraphStyle(name='DP',fontName='Helvetica',fontSize=9,textColor=colors.HexColor('#7F8C8D'),leftIndent=10,spaceAfter=3,leading=12))
        s.add(ParagraphStyle(name='FT',fontName='Helvetica',fontSize=8,textColor=colors.HexColor('#95A5A6'),alignment=TA_CENTER))

    def _hf(self, co, doc, md):
        co.saveState()
        co.setStrokeColor(colors.HexColor('#E0E0E0')); co.setLineWidth(0.5)
        co.line(50,self.height-50,self.width-50,self.height-50)
        co.setFillColor(colors.HexColor(self.branding.primary_color)); co.setFont('Helvetica-Bold',9)
        co.drawString(50,self.height-40,self.branding.company_name)
        co.setFillColor(colors.HexColor('#7F8C8D')); co.setFont('Helvetica',9)
        co.drawRightString(self.width-50,self.height-40,md.get('title','')[:40])
        co.setFillColor(colors.HexColor('#E74C3C')); co.setFont('Helvetica-Bold',7)
        co.drawRightString(self.width-50,self.height-28,'CONFIDENTIAL')
        co.line(50,40,self.width-50,40)
        co.setFillColor(colors.HexColor('#95A5A6')); co.setFont('Helvetica',8)
        co.drawCentredString(self.width/2,25,f"Page {co.getPageNumber()}")
        co.drawString(50,25,f"Generated: {md.get('date','')}")
        if self.branding.website: co.drawRightString(self.width-50,25,self.branding.website)
        co.restoreState()

    def generate(self, output_path):
        op=Path(output_path); op.parent.mkdir(parents=True,exist_ok=True)
        doc=SimpleDocTemplate(str(op),pagesize=self.page_size,rightMargin=50,leftMargin=50,topMargin=60,bottomMargin=50)
        now=datetime.now(); md={'title':'Consumer Sentiment Intelligence Report','date':now.strftime('%Y-%m-%d')}
        cn="Acme Restaurant Group"; rp="January 2026"; tr=15420; la=127; ss=0.72
        pc=9852; nc=3258; ngc=2310; cl=0.95
        kpis=[KPICard("Sentiment Score",0.72,trend=TrendDirection.UP,trend_value=5.2,benchmark=0.65,severity=SeverityLevel.LOW),
              KPICard("Total Reviews",15420,trend=TrendDirection.UP,trend_value=12.3,severity=SeverityLevel.INFO),
              KPICard("Avg Rating",4.2,benchmark=4.0,severity=SeverityLevel.LOW),
              KPICard("Response Rate",87.5,unit="%",trend=TrendDirection.UP,trend_value=3.1,benchmark=75.0,severity=SeverityLevel.LOW),
              KPICard("Anomalies",7,trend=TrendDirection.DOWN,trend_value=-12.5,severity=SeverityLevel.MEDIUM),
              KPICard("NPS Score",62,trend=TrendDirection.UP,trend_value=8.0,benchmark=50,severity=SeverityLevel.LOW)]
        recs=[Recommendation("Improve Response Time to Negative Reviews","Locations with faster response times have 23% higher sentiment recovery.",SeverityLevel.HIGH,"High","Low","Customer Service",
                ["Avg response time: 48h","Best performers: 4h","67% update review after response"],["Automated alerts","Response templates","Staff training"]),
              Recommendation("Address Food Quality in NYC","NYC locations 15% lower food quality sentiment.",SeverityLevel.MEDIUM,"High","Medium","Operations",
                ["NYC: 0.45 vs national 0.60","Complaints: temperature, portions"],["Quality audit","Supply chain review"])]
        bms=[BenchmarkData("Overall Sentiment",0.72,0.65,0.85,68),BenchmarkData("Review Volume",15420,12000,25000,72),
             BenchmarkData("Average Rating",4.2,4.0,4.7,65),BenchmarkData("Response Rate",87.5,75.0,95.0,78),
             BenchmarkData("Customer Loyalty",0.68,0.55,0.82,71)]
        comps=[CompetitorData("Competitor A",0.68,18500,4.1,TrendDirection.STABLE,["Strong brand","Wide menu"],["Inconsistent service","Higher prices"]),
               CompetitorData("Competitor B",0.75,12000,4.3,TrendDirection.UP,["Excellent service","Modern locations"],["Limited locations","Smaller portions"])]
        themes=[{"theme":"Food Quality","frequency":4521,"sentiment":"Positive","trend":"up"},
                {"theme":"Service Speed","frequency":3210,"sentiment":"Mixed","trend":"stable"},
                {"theme":"Cleanliness","frequency":2890,"sentiment":"Positive","trend":"up"},
                {"theme":"Value for Money","frequency":2450,"sentiment":"Neutral","trend":"down"},
                {"theme":"Atmosphere","frequency":1980,"sentiment":"Positive","trend":"stable"},
                {"theme":"Staff Friendliness","frequency":1745,"sentiment":"Positive","trend":"up"},
                {"theme":"Wait Times","frequency":1520,"sentiment":"Negative","trend":"down"},
                {"theme":"Order Accuracy","frequency":1380,"sentiment":"Mixed","trend":"stable"},
                {"theme":"Portion Size","frequency":1105,"sentiment":"Neutral","trend":"down"},
                {"theme":"Menu Variety","frequency":960,"sentiment":"Positive","trend":"up"}]
        locs=[{"name":"Downtown Manhattan","city":"New York","sentiment_score":0.82,"review_count":450,"avg_rating":4.5},
              {"name":"Chicago Loop","city":"Chicago","sentiment_score":0.78,"review_count":380,"avg_rating":4.3},
              {"name":"Beverly Hills","city":"Los Angeles","sentiment_score":0.76,"review_count":290,"avg_rating":4.4},
              {"name":"Back Bay","city":"Boston","sentiment_score":0.74,"review_count":210,"avg_rating":4.2},
              {"name":"Financial District","city":"San Francisco","sentiment_score":0.71,"review_count":340,"avg_rating":4.1},
              {"name":"Times Square","city":"New York","sentiment_score":0.42,"review_count":520,"avg_rating":3.2},
              {"name":"Airport Terminal","city":"Chicago","sentiment_score":0.38,"review_count":180,"avg_rating":3.0},
              {"name":"Mall Location","city":"Houston","sentiment_score":0.35,"review_count":95,"avg_rating":2.9}]
        anoms=[{"type":"Sentiment Drop","location":"Times Square, NYC","severity":"high","detected_at":"2026-02-01","deviation":-28.5,
                "description":"Sudden 28% drop in sentiment over 48 hours. Correlates with staffing changes and new management transition."},
               {"type":"Volume Spike","location":"Chicago Loop","severity":"medium","detected_at":"2026-02-02","deviation":45.0,
                "description":"Unusual 45% increase in review volume. Possible viral social media mention or influencer visit detected."},
               {"type":"Rating Collapse","location":"Airport Terminal, Chicago","severity":"critical","detected_at":"2026-01-28","deviation":-35.2,
                "description":"Average rating dropped from 3.8 to 2.4 over 5 days. 73% of new reviews mention cold food and long wait times during peak hours."},
               {"type":"Sentiment Divergence","location":"Beverly Hills, LA","severity":"medium","detected_at":"2026-01-30","deviation":22.1,
                "description":"Positive sentiment surged 22% above 90-day rolling average. New seasonal menu launch correlates with increased positive mentions of dessert items."},
               {"type":"Review Velocity Anomaly","location":"Mall Location, Houston","severity":"high","detected_at":"2026-02-03","deviation":-52.8,
                "description":"Review volume dropped 53% week-over-week. Possible operational issue or reduced foot traffic. Requires field investigation."},
               {"type":"Competitor Sentiment Shift","location":"Financial District, SF","severity":"medium","detected_at":"2026-02-04","deviation":18.3,
                "description":"Competitor A sentiment in same zip code rose 18% while our location remained flat. Competitor opened renovated store 2 blocks away."},
               {"type":"Keyword Emergence","location":"Downtown Manhattan, NYC","severity":"low","detected_at":"2026-02-05","deviation":12.7,
                "description":"New recurring keyword cluster detected: 'understaffed', 'slow checkout', 'long lines'. Frequency increased 3x in past 10 days."}]
        st2=[("W1",0.64),("W2",0.68),("W3",0.66),("W4",0.72),("W5",0.69),("W6",0.74),("W7",0.71),("W8",0.68),("W9",0.73),("W10",0.75),("W11",0.70),("W12",0.72)]
        ds=["Google Maps"]
        S=self.styles; story=[]

        # Cover
        story+=[Spacer(1,100),Paragraph("Consumer Sentiment Intelligence Report",S['CT']),
                Paragraph(f"Prepared for: <b>{cn}</b>",S['CS']),Paragraph(f"Analysis Period: {rp}",S['CS']),Spacer(1,60)]
        pv=[[k.title,k.format_value()] for k in kpis[:4]]
        pvt=Table(pv,colWidths=[200,100])
        pvt.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),12),
            ('TEXTCOLOR',(0,0),(0,-1),colors.HexColor('#7F8C8D')),('TEXTCOLOR',(1,0),(1,-1),colors.HexColor(self.branding.primary_color)),
            ('FONTNAME',(1,0),(1,-1),'Helvetica-Bold'),('ALIGN',(0,0),(0,-1),'RIGHT'),('ALIGN',(1,0),(1,-1),'LEFT'),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
        story+=[pvt,Spacer(1,80),Paragraph(self.branding.company_name,S['CS'])]
        if self.branding.tagline: story.append(Paragraph(self.branding.tagline,S['FT']))
        story+=[Spacer(1,20),Paragraph(f"Report Generated: {now.strftime('%B %d, %Y at %H:%M UTC')}",S['FT']),PageBreak()]

        # Executive Summary
        story+=[SectionHeaderFlowable("Executive Summary",self.branding,subtitle="Key Performance Indicators & Insights"),Spacer(1,20)]
        rows2=[]; row2=[]
        for k in kpis[:6]:
            row2.append(KPICardFlowable(k,self.branding,width=130,height=85))
            if len(row2)==3: rows2.append(row2); row2=[]
        if row2:
            while len(row2)<3: row2.append(Spacer(130,85))
            rows2.append(row2)
        kt=Table(rows2,colWidths=[140,140,140])
        kt.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
        story+=[kt,Spacer(1,25),Paragraph(f"<b>Overall Assessment:</b> Analysis of <b>{tr:,}</b> reviews across <b>{la}</b> locations reveals a <b>Positive</b> sentiment trend with score <b>{ss:.2f}</b>.<br/><br/>{len(recs)} recommendations. <b>{len(anoms)} anomalies</b> detected.",S['EB']),
                Spacer(1,15),GaugeChart(value=(ss+1)*50,title="Sentiment Score",branding=self.branding,width=250,height=170),PageBreak()]

        # Sentiment Analysis
        story+=[SectionHeaderFlowable("Sentiment Analysis",self.branding,subtitle=f"Based on {tr:,} reviews"),Spacer(1,15)]
        dr=Drawing(400,200); pie=Pie(); pie.x=100; pie.y=30; pie.width=120; pie.height=120
        pie.data=[pc,nc,ngc]; pie.labels=['Positive','Neutral','Negative']; pie.slices.strokeWidth=0.5
        pie.slices[0].fillColor=colors.HexColor('#2ECC71'); pie.slices[1].fillColor=colors.HexColor('#F1C40F')
        pie.slices[2].fillColor=colors.HexColor('#E74C3C'); pie.slices[0].popout=5
        tot=pc+nc+ngc
        for i,ct2 in enumerate([pc,nc,ngc]): pie.labels[i]=f'{pie.labels[i]}\n{ct2/tot*100:.1f}%'
        lg=Legend(); lg.x=280; lg.y=100; lg.dx=8; lg.dy=8; lg.fontSize=9; lg.alignment='right'
        lg.colorNamePairs=[(colors.HexColor('#2ECC71'),f'Positive ({pc:,})'),(colors.HexColor('#F1C40F'),f'Neutral ({nc:,})'),(colors.HexColor('#E74C3C'),f'Negative ({ngc:,})')]
        dr.add(pie); dr.add(lg); dr.add(String(200,180,'Sentiment Distribution',fontName='Helvetica-Bold',fontSize=11,textAnchor='middle'))
        story+=[dr,Spacer(1,20),Paragraph("<b>Sentiment Trend Over Time</b>",S['SS'])]
        td=Drawing(450,180); lc=HorizontalLineChart(); lc.x=50; lc.y=40; lc.width=350; lc.height=120
        lc.data=[[v for _,v in st2]]; lc.categoryAxis.categoryNames=[d2 for d2,_ in st2]
        lc.categoryAxis.labels.angle=45; lc.categoryAxis.labels.fontSize=7; lc.categoryAxis.labels.boxAnchor='ne'
        lc.valueAxis.valueMin=0.60; lc.valueAxis.valueMax=0.80; lc.valueAxis.valueStep=0.02; lc.valueAxis.labels.fontSize=8
        lc.lines[0].strokeColor=colors.HexColor(self.branding.primary_color); lc.lines[0].strokeWidth=2
        td.add(lc); story+=[td,Spacer(1,15),Paragraph("<b>Key Themes Identified</b>",S['SS'])]
        tdr=[['Theme','Frequency','Sentiment','Trend']]
        for th in themes: tdr.append([th['theme'],str(th['frequency']),th['sentiment'],"+" if th['trend']=='up' else "-" if th['trend']=='down' else "="])
        tt=Table(tdr,colWidths=[180,80,80,50])
        tt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(self.branding.primary_color)),('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),('ALIGN',(1,0),(-1,-1),'CENTER'),
            ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#E0E0E0')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F8F9FA')]),
            ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
        story+=[tt,Spacer(1,15)]

        # Recommendations
        story+=[SectionHeaderFlowable("AI-Powered Recommendations",self.branding,subtitle="Actionable insights prioritized by impact"),Spacer(1,15)]
        pcm={SeverityLevel.CRITICAL:'#E74C3C',SeverityLevel.HIGH:'#E67E22',SeverityLevel.MEDIUM:'#F1C40F',SeverityLevel.LOW:'#2ECC71',SeverityLevel.INFO:'#3498DB'}
        for i,r in enumerate(recs,1):
            re=[Paragraph(f'<font color="{pcm.get(r.priority,"#3498DB")}">*</font> <b>{i}. {r.title}</b>',S['RT']),
                Paragraph(r.description,S['EB']),
                Paragraph(f'<font color="#7F8C8D">Impact:</font> <b>{r.impact}</b> | <font color="#7F8C8D">Effort:</font> <b>{r.effort}</b> | <font color="#7F8C8D">Category:</font> <b>{r.category}</b>',S['DP'])]
            for dp in r.data_points[:3]: re.append(Paragraph(f"- {dp}",S['DP']))
            if r.action_items:
                re+=[Spacer(1,5),Paragraph("<b>Recommended Actions:</b>",S['DP'])]
                for a in r.action_items[:3]: re.append(Paragraph(f"  > {a}",S['DP']))
            re.append(Spacer(1,15)); story.append(KeepTogether(re))
        story.append(PageBreak())

        # Benchmarks
        story+=[SectionHeaderFlowable("Industry Benchmarks",self.branding,subtitle="How you compare to industry standards"),Spacer(1,20)]
        for bm in bms: story+=[BenchmarkBarFlowable(bm,self.branding,width=450,height=45),Spacer(1,5)]
        aa=sum(1 for b in bms if b.your_value>=b.industry_avg); ap=sum(b.percentile for b in bms)//len(bms)
        story+=[Spacer(1,20),Paragraph(f"<b>Benchmark Summary:</b> Above average in <b>{aa}/{len(bms)}</b> metrics. Average percentile: <b>P{ap}</b>.",S['IB']),PageBreak()]

        # Competitors
        story+=[SectionHeaderFlowable("Competitor Analysis",self.branding,subtitle="Competitive landscape overview"),Spacer(1,15)]
        cr=[['Competitor','Sentiment','Reviews','Rating','Trend'],[f"{cn} (You)",f"{ss:.2f}",f"{tr:,}","4.2","+"]]
        for c in comps: cr.append([c.name,f"{c.sentiment_score:.2f}",f"{c.review_count:,}",f"{c.avg_rating:.1f}","+" if c.trend==TrendDirection.UP else "-" if c.trend==TrendDirection.DOWN else "="])
        crt=Table(cr,colWidths=[150,80,80,60,50])
        crt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(self.branding.primary_color)),('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('BACKGROUND',(0,1),(-1,1),colors.HexColor('#E8F6F3')),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTNAME',(0,1),(-1,1),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),9),('ALIGN',(1,0),(-1,-1),'CENTER'),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#E0E0E0')),
            ('ROWBACKGROUNDS',(0,2),(-1,-1),[colors.white,colors.HexColor('#F8F9FA')]),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
        story+=[crt,Spacer(1,20)]
        tc=comps[0]; sw=[]
        for i in range(max(len(tc.strengths),len(tc.weaknesses))):
            s2=tc.strengths[i] if i<len(tc.strengths) else ""; w2=tc.weaknesses[i] if i<len(tc.weaknesses) else ""
            sw.append([f"+ {s2}" if s2 else "",f"- {w2}" if w2 else ""])
        story.append(Paragraph(f"<b>{tc.name} - SWOT Overview</b>",S['SS']))
        swt=Table([['Strengths','Weaknesses']]+sw,colWidths=[210,210])
        swt.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),colors.HexColor('#2ECC71')),('BACKGROUND',(1,0),(1,0),colors.HexColor('#E74C3C')),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),
            ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#E0E0E0')),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
            ('TEXTCOLOR',(0,1),(0,-1),colors.HexColor('#27AE60')),('TEXTCOLOR',(1,1),(1,-1),colors.HexColor('#C0392B'))]))
        story+=[swt,PageBreak()]

        # Location Analysis
        story+=[SectionHeaderFlowable("Location Analysis",self.branding,subtitle="Top performing and at-risk locations"),Spacer(1,15)]
        sl=sorted(locs,key=lambda x:x['sentiment_score'],reverse=True)
        story.append(Paragraph("<b>Top Performing Locations</b>",S['SS']))
        tld=[['Location','City','Sentiment','Reviews','Rating']]
        for l in sl[:5]: tld.append([l['name'],l['city'],f"{l['sentiment_score']:.2f}",str(l['review_count']),f"{l['avg_rating']:.1f}"])
        tlt=Table(tld,colWidths=[150,80,70,60,60])
        tlt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#27AE60')),('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),('ALIGN',(2,0),(-1,-1),'CENTER'),
            ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#E0E0E0')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F0FFF0')]),
            ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        story+=[tlt,Spacer(1,20),Paragraph("<b>Locations Requiring Attention</b>",S['SS'])]
        bld=[['Location','City','Sentiment','Reviews','Rating']]
        for l in sl[-3:]: bld.append([l['name'],l['city'],f"{l['sentiment_score']:.2f}",str(l['review_count']),f"{l['avg_rating']:.1f}"])
        blt=Table(bld,colWidths=[150,80,70,60,60])
        blt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E74C3C')),('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),('ALIGN',(2,0),(-1,-1),'CENTER'),
            ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#E0E0E0')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#FFF0F0')]),
            ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        story+=[blt,PageBreak()]

        # Anomalies
        story+=[SectionHeaderFlowable("Anomaly Alerts",self.branding,subtitle=f"{len(anoms)} anomalies detected"),Spacer(1,15)]
        sc3={'critical':'#E74C3C','high':'#E67E22','medium':'#F1C40F','low':'#2ECC71'}
        for an in anoms:
            ac=sc3.get(an.get('severity','medium').lower(),'#F1C40F')
            story+=[Paragraph(f'<font color="{ac}"><b>* {an["type"].upper()}</b></font> - {an["location"]}<br/><font color="#7F8C8D">Detected: {an["detected_at"]} | Deviation: {an["deviation"]:.1f}%</font><br/>{an["description"]}',S['EB']),Spacer(1,10)]
        story.append(PageBreak())

        # Appendix
        story+=[SectionHeaderFlowable("Appendix",self.branding,subtitle="Methodology & Data Sources"),Spacer(1,15),
                Paragraph("<b>Methodology</b>",S['SS']),
                Paragraph(f"This report analyzes {tr:,} reviews from {len(ds)} sources across {la} locations.<br/><br/>- <b>MiniLM embeddings</b> (384-dim vectors)<br/>- <b>Isolation Forest</b> anomaly detection<br/>- <b>Welford's algorithm</b> incremental stats<br/>- <b>Confidence:</b> {cl*100:.0f}%",S['EB']),
                Spacer(1,20),Paragraph("<b>Data Sources</b>",S['SS'])]
        for src in ds: story.append(Paragraph(f"- {src}",S['DP']))
        story+=[Spacer(1,20),Paragraph("<b>Disclaimer</b>",S['SS']),
                Paragraph("This report is for informational purposes only and should not be considered investment advice. Past performance is not indicative of future results.",S['DP'])]

        doc.build(story,onFirstPage=lambda c2,d2:None,onLaterPages=lambda c2,d2:self._hf(c2,d2,md))
        fs=op.stat().st_size
        print(f"Report generated successfully!")
        print(f"  Output: {op}")
        print(f"  Client: {cn}")
        print(f"  Period: {rp}")
        print(f"  Reviews: {tr:,}")
        print(f"  Locations: {la}")
        print(f"  Sentiment: {ss:.2f} (Positive)")
        print(f"  File size: {fs:,} bytes ({fs/1024:.1f} KB)")
        return op

if __name__ == "__main__":
    out="/home/info_betsim/reviewsignal-5.0/reports/sample_enterprise_report.pdf"
    if len(sys.argv)>1: out=sys.argv[1]
    g=SampleReportGenerator(BrandingConfig())
    g.generate(out)
