import os
import re
from flask import Flask, redirect, render_template, request, session, url_for
from dotenv import load_dotenv
from google import genai
from markupsafe import Markup, escape

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-this-for-production")

api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key) if api_key else None


def format_study_answer(text):
    """Safely turn simple Markdown responses into readable study notes."""
    blocks, list_items = [], []

    def finish_list():
        nonlocal list_items
        if list_items:
            blocks.append("<ul>" + "".join(list_items) + "</ul>")
            list_items = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            finish_list()
            continue

        safe_line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", str(escape(line)))
        if safe_line.startswith("### "):
            finish_list(); blocks.append(f"<h4>{safe_line[4:]}</h4>")
        elif safe_line.startswith("## "):
            finish_list(); blocks.append(f"<h3>{safe_line[3:]}</h3>")
        elif safe_line.startswith("# "):
            finish_list(); blocks.append(f"<h2>{safe_line[2:]}</h2>")
        elif re.match(r"^[-*•]\s+", safe_line):
            bullet_text = re.sub(r"^[-*•]\s+", "", safe_line)
            list_items.append(f"<li>{bullet_text}</li>")
        else:
            finish_list(); blocks.append(f"<p>{safe_line}</p>")

    finish_list()
    return Markup("".join(blocks))


@app.route("/", methods=["GET", "POST"])
def home():
    messages = session.get("messages", [])

    if request.method == "POST":
        question = request.form.get("question", "").strip()

        if question:
            try:
                if client is None:
                    raise RuntimeError("Missing GEMINI_API_KEY")
                response = client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=(
                        "You are a helpful AI study assistant. Give accurate, clear, well-structured "
                        "answers. Use a short descriptive heading, then brief paragraphs. Use bullet "
                        "points for key ideas, steps, examples, or takeaways when useful. Keep the "
                        "answer focused and do not use a heading named 'Answer'.\n\nStudent question: "
                        + question
                    )
                )

                answer = str(format_study_answer(response.text))

            except Exception:
                answer = "Gemini is temporarily unavailable. Please check your API key and try again in a few seconds."

            messages.append({"question": question, "answer": answer})
            # Keep a useful recent history without letting the cookie grow indefinitely.
            session["messages"] = messages[-12:]
            session.modified = True
            return redirect(url_for("home"))

    return render_template("index.html", messages=messages)


@app.post("/new-chat")
def new_chat():
    """Start a fresh study conversation without changing AI configuration."""
    session.pop("messages", None)
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
