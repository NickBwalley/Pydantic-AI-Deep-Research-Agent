import os
import re
import gradio as gr
from dotenv import load_dotenv
from datetime import datetime
from fpdf import FPDF

from research_agent import deep_research, ResearchReport

load_dotenv()

# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    """Strip Markdown syntax and encode to Latin-1 safe characters."""
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = text.strip()
    return text.encode('latin-1', errors='replace').decode('latin-1')


def generate_pdf(report: ResearchReport, query: str) -> str:
    now = datetime.now()
    filename = f"research_report_{now.strftime('%Y%m%d_%H%M%S')}.pdf"
    display_dt = now.strftime("%B %d, %Y  |  %H:%M:%S")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 18, 18)
    pdf.add_page()

    # ---- Title block -------------------------------------------------------
    pdf.set_font("Helvetica", "B", 20)
    pdf.multi_cell(0, 12, _clean(f"Research Report: {query}"), align="C")
    pdf.ln(3)

    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 6, f"Generated: {display_dt}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_draw_color(180, 180, 180)
    pdf.line(18, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(8)

    # ---- Executive Summary -------------------------------------------------
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, "Executive Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, _clean(report.executive_summary))
    pdf.ln(8)

    # ---- Research Sections -------------------------------------------------
    for section in report.sections:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 9, _clean(section.title), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _clean(section.content))
        pdf.ln(3)

        if section.sources:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, "Sources:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 8)
            for src in section.sources:
                safe_src = src.encode('latin-1', errors='replace').decode('latin-1')
                # Truncate very long URLs to prevent overflow
                if len(safe_src) > 100:
                    safe_src = safe_src[:97] + "..."
                pdf.multi_cell(0, 5, f"  • {safe_src}")
        pdf.ln(8)

    # ---- Risks & Uncertainties ---------------------------------------------
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 9, "Risks & Uncertainties", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, _clean(report.risks_uncertainties))
    pdf.ln(8)

    # ---- What to Watch Next ------------------------------------------------
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 9, "What to Watch Next", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    for item in report.what_to_watch_next:
        pdf.multi_cell(0, 6, f"  • {_clean(item)}")
    pdf.ln(4)

    # ---- Footer timestamp on last page is handled by FPDF auto page break --

    pdf.output(filename)
    return filename


# ---------------------------------------------------------------------------
# Gradio event handler
# ---------------------------------------------------------------------------

async def interact(user_message, history):
    if not user_message:
        yield history, "", gr.update(visible=False)
        return

    history = history or []
    history.append({"role": "user", "content": user_message})
    yield history, "", gr.update(visible=False)

    async for update in deep_research(user_message):
        if isinstance(update, str):
            if history[-1]["role"] != "assistant":
                history.append({"role": "assistant", "content": update})
            else:
                history[-1]["content"] = update
            yield history, "", gr.update(visible=False)

        elif isinstance(update, ResearchReport):
            # Build Markdown report for the chat
            report_md = f"# Research Report: {user_message}\n\n"
            report_md += f"*Generated: {datetime.now().strftime('%B %d, %Y at %H:%M:%S')}*\n\n"
            report_md += f"## Executive Summary\n{update.executive_summary}\n\n"

            for section in update.sections:
                report_md += f"### {section.title}\n{section.content}\n\n"
                if section.sources:
                    report_md += "**Sources:**\n" + "\n".join([f"- {s}" for s in section.sources]) + "\n\n"

            report_md += f"## Risks & Uncertainties\n{update.risks_uncertainties}\n\n"
            report_md += "## What to Watch Next\n" + "\n".join([f"- {item}" for item in update.what_to_watch_next])

            history[-1]["content"] = report_md

            pdf_path = generate_pdf(update, user_message)
            yield history, "", gr.update(value=pdf_path, visible=True)


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

with gr.Blocks() as demo:
    gr.Markdown("# Pydantic AI Deep Research Agent")
    gr.Markdown("Ask about any company, person, technology, event, concept, or topic to generate a detailed research report.")

    chatbot = gr.Chatbot(label="Agent", height=700)
    msg = gr.Textbox(
        placeholder="e.g. NVIDIA, quantum computing, Elon Musk, Paris Agreement...",
        label="Research Query"
    )
    download_btn = gr.DownloadButton(
        label="Download PDF Report",
        visible=False,
    )

    msg.submit(
        interact,
        inputs=[msg, chatbot],
        outputs=[chatbot, msg, download_btn],
    )

if __name__ == "__main__":
    demo.launch()
