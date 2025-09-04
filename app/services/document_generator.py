"""
Document Generation Service for Madagascar License System
Standardized PDF document generation using ReportLab
"""

import io
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect

logger = logging.getLogger(__name__)

class DocumentTemplate:
    """Base class for document templates"""
    
    def __init__(self, title: str, page_size=A4):
        self.title = title
        self.page_size = page_size
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
    
    def setup_custom_styles(self):
        """Setup custom styles for Madagascar documents"""
        
        # Government header style - National level
        self.styles.add(ParagraphStyle(
            name='GovernmentHeader',
            parent=self.styles['Heading1'],
            fontSize=20,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=4,
            textColor=colors.Color(0.1, 0.2, 0.5, 1),  # Deep government blue
            letterSpacing=1
        ))
        
        # Department header style - Ministry level
        self.styles.add(ParagraphStyle(
            name='DepartmentHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=4,
            textColor=colors.Color(0.2, 0.3, 0.6, 1),  # Medium government blue
            letterSpacing=0.5
        ))
        
        # Office header style - Department level
        self.styles.add(ParagraphStyle(
            name='OfficeHeader',
            parent=self.styles['Heading3'],
            fontSize=14,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=8,
            textColor=colors.Color(0.3, 0.4, 0.7, 1),  # Lighter government blue
        ))
        
        # Official title style - Document type
        self.styles.add(ParagraphStyle(
            name='OfficialTitle',
            parent=self.styles['Heading2'],
            fontSize=18,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            textColor=colors.Color(0.8, 0.1, 0.1, 1),  # Official red
            borderColor=colors.Color(0.1, 0.2, 0.5, 1),  # Government blue border
            borderWidth=3,
            borderPadding=12,
            backColor=colors.Color(0.95, 0.95, 0.98, 1),  # Very light blue background
            spaceAfter=20,
            spaceBefore=10
        ))
        
        # Field label style
        self.styles.add(ParagraphStyle(
            name='FieldLabel',
            parent=self.styles['Normal'],
            fontSize=11,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT,
            textColor=colors.Color(0.1, 0.2, 0.5, 1),  # Government blue for labels
            spaceAfter=2
        ))
        
        # Field value style
        self.styles.add(ParagraphStyle(
            name='FieldValue',
            parent=self.styles['Normal'],
            fontSize=11,
            fontName='Helvetica',
            alignment=TA_LEFT,
            textColor=colors.Color(0.1, 0.1, 0.1, 1),  # Dark grey for values
            spaceAfter=2
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Normal'],
            fontSize=12,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT,
            textColor=colors.Color(0.1, 0.2, 0.5, 1),  # Government blue
            backColor=colors.Color(0.92, 0.94, 0.98, 1),  # Light blue background
            borderColor=colors.Color(0.1, 0.2, 0.5, 1),
            borderWidth=1,
            borderPadding=6,
            spaceAfter=8,
            spaceBefore=4
        ))
        
        # Footer style
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=9,
            fontName='Helvetica',
            alignment=TA_CENTER,
            textColor=colors.Color(0.4, 0.4, 0.4, 1),  # Grey footer text
            spaceAfter=4,
            spaceBefore=2
        ))
        
        # Official stamp style
        self.styles.add(ParagraphStyle(
            name='OfficialStamp',
            parent=self.styles['Normal'],
            fontSize=8,
            fontName='Helvetica-Oblique',
            alignment=TA_CENTER,
            textColor=colors.Color(0.5, 0.5, 0.5, 1),  # Light grey
            spaceAfter=6
        ))

class ReceiptTemplate(DocumentTemplate):
    """Receipt document template for Madagascar transactions"""
    
    def generate(self, data: Dict[str, Any]) -> bytes:
        """Generate receipt PDF from transaction data"""
        try:
            logger.info(f"Generating receipt PDF for transaction: {data.get('transaction_number', 'Unknown')}")
            
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=self.page_size,
                rightMargin=20*mm,
                leftMargin=20*mm,
                topMargin=20*mm,
                bottomMargin=20*mm,
                title=self.title
            )
            
            story = []
            
            # Government headers with coat of arms placeholder
            story.append(Paragraph(data.get('government_header', 'REPOBLIKAN\'I MADAGASIKARA'), self.styles['GovernmentHeader']))
            story.append(Paragraph(data.get('department_header', 'MINISTÈRE DES TRANSPORTS, DU TOURISME ET DE LA MÉTÉOROLOGIE'), self.styles['DepartmentHeader']))
            story.append(Paragraph(data.get('office_header', 'Direction Générale des Transports Terrestres'), self.styles['OfficeHeader']))
            story.append(Spacer(1, 8))
            
            # Separator line
            separator_table = Table([['']], colWidths=[170*mm])
            separator_table.setStyle(TableStyle([
                ('LINEBELOW', (0, 0), (-1, -1), 2, colors.Color(0.1, 0.2, 0.5, 1)),
            ]))
            story.append(separator_table)
            story.append(Spacer(1, 15))
            
            # Receipt title with official styling
            story.append(Paragraph(data.get('receipt_title', 'REÇU OFFICIEL DE PAIEMENT'), self.styles['OfficialTitle']))
            story.append(Spacer(1, 15))
            
            # Receipt details table with official styling
            receipt_details = [
                [
                    Paragraph('<b>N° de Reçu:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('receipt_number', 'N/A')), self.styles['FieldValue']),
                    Paragraph('<b>Date & Heure:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('date', 'N/A')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>N° de Transaction:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('transaction_number', 'N/A')), self.styles['FieldValue']),
                    Paragraph('<b>Bureau:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('location', 'N/A')), self.styles['FieldValue'])
                ]
            ]
            
            receipt_table = Table(receipt_details, colWidths=[40*mm, 45*mm, 35*mm, 50*mm])
            receipt_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.97, 0.98, 1.0, 1)),  # Very light blue
                ('BOX', (0, 0), (-1, -1), 1, colors.Color(0.1, 0.2, 0.5, 1)),  # Government blue border
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.Color(0.8, 0.8, 0.9, 1)),  # Light grid lines
            ]))
            
            story.append(receipt_table)
            story.append(Spacer(1, 18))
            
            # Customer information section with official header
            story.append(Paragraph('INFORMATIONS DU BÉNÉFICIAIRE', self.styles['SectionHeader']))
            story.append(Spacer(1, 8))
            
            customer_data = [
                [
                    Paragraph('<b>Nom et Prénoms:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('person_name', 'N/A')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>Numéro CIN/Passeport:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('person_id', 'N/A')), self.styles['FieldValue'])
                ]
            ]
            
            customer_table = Table(customer_data, colWidths=[50*mm, 120*mm])
            customer_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('BOX', (0, 0), (-1, -1), 2, colors.Color(0.1, 0.2, 0.5, 1)),  # Government blue border
                ('INNERGRID', (0, 0), (-1, -1), 1, colors.Color(0.7, 0.7, 0.8, 1)),  # Light grid
                ('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.95, 0.97, 1.0, 1)),  # Very light blue
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ]))
            
            story.append(customer_table)
            story.append(Spacer(1, 18))
            
            # Payment items section with official header
            story.append(Paragraph('DÉTAIL DES PAIEMENTS', self.styles['SectionHeader']))
            story.append(Spacer(1, 8))
            
            # Build payment items table with official styling
            payment_data = [
                [
                    Paragraph('<b>Service / Prestation</b>', self.styles['FieldLabel']),
                    Paragraph(f'<b>Montant ({data.get("currency", "Ariary")})</b>', self.styles['FieldLabel'])
                ]
            ]
            
            # Add items
            items = data.get('items', [])
            for item in items:
                payment_data.append([
                    Paragraph(str(item.get('description', 'N/A')), self.styles['FieldValue']),
                    Paragraph(f"{item.get('amount', 0):,.0f}", self.styles['FieldValue'])
                ])
            
            # Add total row with emphasis
            payment_data.append([
                Paragraph('<b>MONTANT TOTAL À PAYER</b>', self.styles['FieldLabel']),
                Paragraph(f"<b>{data.get('total_amount', 0):,.0f}</b>", self.styles['FieldLabel'])
            ])
            
            payment_table = Table(payment_data, colWidths=[110*mm, 60*mm])
            payment_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                # Header row styling
                ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.1, 0.2, 0.5, 1)),  # Government blue header
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                # Data rows styling
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('BACKGROUND', (0, 1), (-1, -2), colors.Color(0.98, 0.99, 1.0, 1)),  # Very light blue for data
                # Total row styling
                ('BACKGROUND', (0, -1), (-1, -1), colors.Color(0.85, 0.9, 0.95, 1)),  # Light blue for total
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.Color(0.1, 0.2, 0.5, 1)),  # Government blue text
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, -1), (-1, -1), 12),
                # Borders and padding
                ('BOX', (0, 0), (-1, -1), 2, colors.Color(0.1, 0.2, 0.5, 1)),  # Government blue border
                ('INNERGRID', (0, 0), (-1, -1), 1, colors.Color(0.6, 0.7, 0.8, 1)),  # Light grid lines
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ]))
            
            story.append(payment_table)
            story.append(Spacer(1, 18))
            
            # Payment method section with official header
            story.append(Paragraph('MODALITÉS DE PAIEMENT', self.styles['SectionHeader']))
            story.append(Spacer(1, 8))
            
            payment_method_data = [
                [
                    Paragraph('<b>Mode de Paiement:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('payment_method', 'N/A')), self.styles['FieldValue'])
                ]
            ]
            
            if data.get('payment_reference'):
                payment_method_data.append([
                    Paragraph('<b>Référence:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('payment_reference')), self.styles['FieldValue'])
                ])
            
            payment_method_data.append([
                Paragraph('<b>Traité par:</b>', self.styles['FieldLabel']),
                Paragraph(str(data.get('processed_by', 'Système')), self.styles['FieldValue'])
            ])
            
            payment_method_table = Table(payment_method_data, colWidths=[50*mm, 120*mm])
            payment_method_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.93, 0.96, 1.0, 1)),  # Light blue
                ('BOX', (0, 0), (-1, -1), 2, colors.Color(0.1, 0.2, 0.5, 1)),  # Government blue border
                ('INNERGRID', (0, 0), (-1, -1), 1, colors.Color(0.7, 0.7, 0.8, 1)),  # Light grid
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            
            story.append(payment_method_table)
            story.append(Spacer(1, 25))
            
            # Official verification stamp area
            story.append(Paragraph('CACHET ET SIGNATURE OFFICIELS', self.styles['OfficialStamp']))
            story.append(Spacer(1, 25))
            
            # Official footer with government branding
            footer_separator = Table([['']], colWidths=[170*mm])
            footer_separator.setStyle(TableStyle([
                ('LINEABOVE', (0, 0), (-1, -1), 1, colors.Color(0.1, 0.2, 0.5, 1)),
            ]))
            story.append(footer_separator)
            story.append(Spacer(1, 8))
            
            story.append(Paragraph(data.get('footer', 'République de Madagascar - Reçu Officiel du Gouvernement'), self.styles['Footer']))
            story.append(Paragraph(data.get('validity_note', 'Ce reçu est valide et doit être conservé pour vos dossiers'), self.styles['Footer']))
            story.append(Paragraph(data.get('contact_info', 'Pour assistance: +261 20 22 123 45 | transport@gov.mg'), self.styles['Footer']))
            story.append(Spacer(1, 8))
            story.append(Paragraph('Document généré électroniquement - Aucune signature manuscrite requise', self.styles['OfficialStamp']))
            
            # Build PDF
            doc.build(story)
            buffer.seek(0)
            pdf_data = buffer.getvalue()
            buffer.close()
            
            logger.info(f"Successfully generated receipt PDF ({len(pdf_data)} bytes)")
            return pdf_data
            
        except Exception as e:
            logger.error(f"Error generating receipt PDF: {e}")
            raise Exception(f"PDF generation failed: {str(e)}")

class DocumentGenerator:
    """Main document generator service"""
    
    def __init__(self):
        self.version = "1.0.0"
        logger.info("Document Generator Service initialized")
    
    def generate_receipt(self, data: Dict[str, Any]) -> bytes:
        """Generate receipt PDF"""
        template = ReceiptTemplate("Madagascar Official Receipt")
        return template.generate(data)
    
    def get_sample_receipt_data(self) -> Dict[str, Any]:
        """Generate sample receipt data for testing"""
        return {
            'government_header': 'REPOBLIKAN\'I MADAGASIKARA',
            'department_header': 'MINISTÈRE DES TRANSPORTS, DU TOURISME ET DE LA MÉTÉOROLOGIE',
            'office_header': 'Direction Générale des Transports Terrestres',
            'receipt_title': 'REÇU OFFICIEL DE PAIEMENT',
            'receipt_number': f'RCT-{datetime.now().strftime("%Y%m%d")}-001',
            'transaction_number': f'TXN-{datetime.now().strftime("%Y%m%d")}-001',
            'date': datetime.now().strftime('%d/%m/%Y à %H:%M'),
            'location': 'Bureau Central Antananarivo',
            'person_name': 'RAKOTOARISOA Jean Baptiste',
            'person_id': '101 234 567 890',
            'currency': 'Ariary',
            'items': [
                {
                    'description': 'Frais de demande de permis de conduire',
                    'amount': 38000
                },
                {
                    'description': 'Examen théorique',
                    'amount': 10000
                },
                {
                    'description': 'Examen pratique',
                    'amount': 10000
                }
            ],
            'total_amount': 58000,
            'payment_method': 'Espèces',
            'payment_reference': None,
            'processed_by': 'ANDRIANJAFY Marie Célestine',
            'footer': 'République de Madagascar - Reçu Officiel du Gouvernement',
            'validity_note': 'Ce reçu est valide et doit être conservé pour vos dossiers',
            'contact_info': 'Pour assistance: +261 20 22 123 45 | transport@gov.mg'
        }

# Service instance
document_generator = DocumentGenerator()
