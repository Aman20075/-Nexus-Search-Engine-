import tkinter as tk
from tkinter import messagebox
import sqlite3
import webbrowser

def search_and_rank():
    query = search_entry.get().strip().lower()
    result_box.delete("1.0", tk.END)
    
    if not query:
        result_box.insert(tk.END, "⚠️ Kripya koi word search box me type karein!\n", "warning")
        return

    try:
        conn = sqlite3.connect("search_engine.db")
        cursor = conn.cursor()
        cursor.execute("SELECT title, url, snippet FROM pages")
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.OperationalError:
        messagebox.showerror("Error", "'search_engine.db' nahi mili! Pehle crawler.py chalao.")
        return

    ranked_results = []

    # Relevance Ranking Logic (Keyword Frequency Score)
    for title, url, snippet in rows:
        title_lower = title.lower()
        snippet_lower = snippet.lower()
        
        # Scoring: Title me match = 3 points, Snippet me match = 1 point
        score = (title_lower.count(query) * 3) + snippet_lower.count(query)

        if score > 0:
            ranked_results.append((score, title, url, snippet))

    # Highest score wale result ko pehle dikhana (Sorting)
    ranked_results.sort(key=lambda x: x[0], reverse=True)

    result_box.insert(tk.END, f"🔎 Search Results for: '{query}' ({len(ranked_results)} found)\n", "header")
    result_box.insert(tk.END, "━"*55 + "\n\n", "border")

    if not ranked_results:
        result_box.insert(tk.END, "❌ Koi bhi matching result nahi mila.", "warning")
        return

    for rank, (score, title, url, snippet) in enumerate(ranked_results, start=1):
        result_box.insert(tk.END, f"[{rank}] {title} (Score: {score})\n", "title")
        
        # Clickable URL Link create karna
        start_idx = result_box.index(tk.END)
        result_box.insert(tk.END, f"🔗 {url}\n", "url")
        end_idx = result_box.index(tk.END)
        
        # Hyperlink Tag Assignment
        tag_name = f"link_{rank}"
        result_box.tag_add(tag_name, start_idx, end_idx)
        result_box.tag_config(tag_name, foreground="#89b4fa", underline=True)
        
        # Click handler attach karna
        result_box.tag_bind(tag_name, "<Button-1>", lambda e, link=url: open_browser(link))
        result_box.tag_bind(tag_name, "<Enter>", lambda e: result_box.config(cursor="hand2"))
        result_box.tag_bind(tag_name, "<Leave>", lambda e: result_box.config(cursor=""))

        result_box.insert(tk.END, f"📄 {snippet}\n", "snippet")
        result_box.insert(tk.END, "-"*55 + "\n\n", "border")

def open_browser(url):
    webbrowser.open(url)

# GUI Dark Theme Setup
root = tk.Tk()
root.title("Nexus Search Engine Pro ⚡")
root.geometry("680x580")
root.configure(bg="#1e1e2e")

title_label = tk.Label(
    root, text="⚡ NEXUS SEARCH PRO", 
    font=("Segoe UI", 18, "bold"), 
    bg="#1e1e2e", fg="#cba6f7"
)
title_label.pack(pady=15)

frame = tk.Frame(root, bg="#1e1e2e")
frame.pack(pady=5)

search_entry = tk.Entry(
    frame, font=("Segoe UI", 12), width=35, 
    bg="#313244", fg="#cdd6f4", insertbackground="white", 
    relief="flat", bd=5
)
search_entry.pack(side=tk.LEFT, padx=5)

search_button = tk.Button(
    frame, text="Search 🔍", font=("Segoe UI", 10, "bold"), 
    bg="#89b4fa", fg="#11111b", activebackground="#b4befe", 
    relief="flat", cursor="hand2", command=search_and_rank
)
search_button.pack(side=tk.LEFT, padx=5)

result_box = tk.Text(
    root, font=("Consolas", 10), width=75, height=21, 
    bg="#181825", fg="#cdd6f4", relief="flat", bd=10, padx=10, pady=10
)
result_box.pack(pady=15, padx=15)

# Styling Tags
result_box.tag_config("header", foreground="#f9e2af", font=("Segoe UI", 11, "bold"))
result_box.tag_config("title", foreground="#a6e3a1", font=("Segoe UI", 10, "bold"))
result_box.tag_config("snippet", foreground="#bac2de")
result_box.tag_config("border", foreground="#45475a")
result_box.tag_config("warning", foreground="#f38ba8")

root.mainloop()