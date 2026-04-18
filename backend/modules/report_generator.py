"""
report_generator.py
===================
Generates a formatted PDF report from analysis results.
"""

from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY


# =============================================================================
# Function: Generate Summary Report PDF
# =============================================================================

def generate_summary_report_pdf(
    results: dict,
    output_path: str,
    paper_name: str = "Research Paper"
) -> str:
    """
    Create a formatted summary report PDF with all findings, suggestions, and score.
    
    Args:
        results: Analysis results from /api/analyze (contains issues, summary, standard)
        output_path: Where to save the summary report PDF
        paper_name: Name of the paper (optional)
    
    Returns:
        Path to the generated summary report PDF
    """
    try:
        doc = SimpleDocTemplate(output_path, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        styles = getSampleStyleSheet()
        
        # ── Custom styles ──
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=28,
            textColor=colors.HexColor("#e5322d"),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor("#333333"),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica'
        )
        
        heading_style = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor("#e5322d"),
            spaceAfter=6,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['BodyText'],
            fontSize=11,
            leading=14,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
            fontName='Helvetica'
        )
        
        # ── Title Section ──
        story.append(Paragraph("Research Paper Analysis Report", title_style))
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph(f"Paper: <b>{paper_name}</b>", subtitle_style))
        story.append(Paragraph(f"Analysis Date: {datetime.now().strftime('%B %d, %Y')}", subtitle_style))
        story.append(Spacer(1, 0.15*inch))
        
        # ── Summary Stats ──
        summary = results.get("summary", {})
        
        # Create summary table
        summary_data = [
            ["Metric", "Value"],
            ["Citation Standard", results.get("standard", "IEEE")],
            ["Total Issues Found", str(summary.get("total", 0))],
            ["Critical Issues", str(summary.get("critical", 0))],
            ["Warnings", str(summary.get("warning", 0))],
            ["Info Messages", str(summary.get("info", 0))],
            ["Overall Score", f"{summary.get('score', 'N/A')}/100"],
        ]
        
        summary_table = Table(summary_data, colWidths=[2.5*inch, 2.5*inch])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5322d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 12),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 1, colors.grey),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 11),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 0.2*inch))
        
        # ── Detailed Findings ──
        issues = results.get("issues", {})
        
        for category in ["grammar", "formatting", "citations"]:
            category_issues = issues.get(category, [])
            
            if category_issues:
                story.append(Paragraph(f"{category.title()} Issues", heading_style))
                
                for idx, issue in enumerate(category_issues, 1):
                    severity = issue.get("severity", "info").upper()
                    message = issue.get("message", "No message")
                    snippet = issue.get("snippet", "")
                    suggestion = issue.get("suggestion", "")
                    page = issue.get("page", "N/A")
                    
                    # Issue header with severity badge
                    issue_header = f"""
                    <b>[{severity}]</b> {message}
                    <br/>
                    <font size="9" color="#666666">Page: {page}</font>
                    """
                    story.append(Paragraph(issue_header, body_style))
                    
                    if snippet:
                        story.append(Paragraph(f"<i>Snippet:</i> \"{snippet}\"", body_style))
                    
                    if suggestion:
                        story.append(Paragraph(f"<b>Suggestion:</b> {suggestion}", body_style))
                    
                    story.append(Spacer(1, 0.08*inch))
        
        # ── Error section (if any) ──
        errors = issues.get("errors", [])
        if errors:
            story.append(Paragraph("System Errors", heading_style))
            for error in errors:
                error_text = f"<b>{error.get('module', 'Unknown')}:</b> {error.get('error', 'Unknown error')}"
                story.append(Paragraph(error_text, body_style))
            story.append(Spacer(1, 0.1*inch))
        
        # ── Footer ──
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph("_" * 80, body_style))
        story.append(Spacer(1, 0.1*inch))
        
        score = float(summary.get("score", 0))
        if score >= 80:
            feedback = "Excellent work! Your paper meets high standards."
        elif score >= 60:
            feedback = "Good job! Address the critical issues to improve further."
        elif score >= 40:
            feedback = "Fair. Please review and address the critical issues."
        else:
            feedback = "Needs significant improvements. Please address the critical issues."
        
        story.append(Paragraph(f"<b>Final Score: {summary.get('score', 'N/A')}/100</b>", heading_style))
        story.append(Spacer(1, 0.05*inch))
        story.append(Paragraph(feedback, body_style))
        
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Thank you for using the Research Paper Checker!", subtitle_style))
        story.append(Paragraph("Good luck with your submission!", subtitle_style))
        
        # ── Build PDF ──
        doc.build(story)
        return output_path
    
    except Exception as e:
        raise Exception(f"Failed to generate summary report PDF: {str(e)}")


# =============================================================================
# Main Function: Generate Summary Report
# =============================================================================
