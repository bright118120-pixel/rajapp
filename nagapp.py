"""
nagapp.py - Streamlit UI for the multi-user Personal Finance Tracker.

Run with:  streamlit run nagapp.py
Streamlit re-runs this whole file from top to bottom every time you click
something. That is why we read the data from the database on every run.
"""

import sqlite3
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

import nagdatabase as db

# ---------------------------------------------------------------- settings
CURRENCY = "₹"  # change to "$", "€", etc. if you like
INCOME_COLOR = "#10B981"
EXPENSE_COLOR = "#EF4444"
COLOR_MAP = {"Income": INCOME_COLOR, "Expense": EXPENSE_COLOR}

st.set_page_config(
    page_title="Personal Finance Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="auto",  # sidebar collapses automatically on phones
)

db.init_db()  # creates the tables if they do not exist yet


# ---------------------------------------------------------------- helpers

PALETTE = ["#6366F1", "#EC4899", "#F59E0B", "#10B981", "#06B6D4", "#8B5CF6", "#EF4444"]
CATEGORY_ICONS = {
    "Salary": "💼", "Freelance": "💻", "Other income": "🎁",
    "Food": "🍔", "Rent": "🏠", "Travel": "✈️", "Shopping": "🛍️",
    "Bills": "🧾", "Education": "🎓", "Other": "📦",
}


def inject_css():
    """Custom look: gradient banner, colourful cards, rounded buttons."""
    st.markdown(
        "<style>"
        "#MainMenu, footer {visibility: hidden;}"
        ".block-container {padding-top: 1.5rem; max-width: 1200px;}"
        ".hero {background: linear-gradient(135deg,#4F46E5 0%,#7C3AED 55%,#EC4899 100%);"
        " border-radius: 20px; padding: 1.5rem 1.8rem; margin-bottom: 1.2rem;"
        " box-shadow: 0 10px 30px rgba(79,70,229,.28);}"
        ".hero h1 {margin: 0; padding: 0; font-size: 1.9rem; color: #fff;}"
        ".hero p {margin: .35rem 0 0 0; color: #fff; opacity: .92;}"
        ".kpi {border-radius: 18px; padding: 1.1rem 1.3rem; color: #fff;"
        " box-shadow: 0 8px 20px rgba(0,0,0,.14); margin-bottom: .8rem;}"
        ".kpi .label {font-size: .85rem; opacity: .92;}"
        ".kpi .value {font-size: 1.75rem; font-weight: 700; margin-top: .15rem;}"
        ".kpi.income {background: linear-gradient(135deg,#10B981,#047857);}"
        ".kpi.expense {background: linear-gradient(135deg,#F87171,#DC2626);}"
        ".kpi.balance {background: linear-gradient(135deg,#6366F1,#4338CA);}"
        ".kpi.savings {background: linear-gradient(135deg,#FBBF24,#D97706);}"
        ".pbar {background: rgba(128,128,128,.25); border-radius: 999px; height: 16px; overflow: hidden;}"
        ".pbar > div {height: 100%; border-radius: 999px;}"
        "div[data-testid='stMetric'] {background: rgba(128,128,128,.09); border-radius: 14px; padding: .8rem 1rem;}"
        "div[data-testid='stForm'] {border-radius: 16px; padding: 1.2rem;}"
        ".stButton > button, .stFormSubmitButton > button, .stDownloadButton > button"
        " {border-radius: 12px; font-weight: 600;}"
        "</style>",
        unsafe_allow_html=True,
    )


def hero(title, subtitle=""):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>',
                unsafe_allow_html=True)


def kpi(label, value, kind, icon):
    st.markdown(
        f'<div class="kpi {kind}"><div class="label">{icon} {label}</div>'
        f'<div class="value">{value}</div></div>',
        unsafe_allow_html=True,
    )


def progress_bar(ratio):
    """Coloured bar: green < 80%, amber < 100%, red when over."""
    color = "#10B981" if ratio < 0.8 else "#F59E0B" if ratio <= 1 else "#EF4444"
    width = min(ratio, 1.0) * 100
    st.markdown(f'<div class="pbar"><div style="width:{width:.0f}%;background:{color}"></div></div>',
                unsafe_allow_html=True)

inject_css()


def money(value):
    """Format a number as money, e.g. ₹12,500.00"""
    return f"{CURRENCY}{value:,.2f}"


def totals(df):
    """Return (income, expense, balance, savings_percent) for a DataFrame."""
    income = df.loc[df["type"] == "Income", "amount"].sum()
    expense = df.loc[df["type"] == "Expense", "amount"].sum()
    balance = income - expense
    savings_pct = (balance / income * 100) if income > 0 else 0.0
    return income, expense, balance, savings_pct


def show_table(df):
    """Display transactions in a clean table."""
    view = df[["date", "description", "category", "type", "amount"]].copy()
    view["date"] = view["date"].dt.strftime("%Y-%m-%d")
    view.columns = ["Date", "Description", "Category", "Income/Expense", "Amount"]
    pretty = view.copy()
    pretty["Category"] = pretty["Category"].map(lambda c: f"{CATEGORY_ICONS.get(c, '')} {c}")
    pretty["Income/Expense"] = pretty["Income/Expense"].map(
        lambda t: "🟢 Income" if t == "Income" else "🔴 Expense")
    st.dataframe(
        pretty,
        hide_index=True,
        column_config={"Amount": st.column_config.NumberColumn(format=f"{CURRENCY}%.2f")},
    )
    return view


def style_figure(fig):
    """Make Plotly charts look good on small screens (legend below chart)."""
    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", y=-0.2),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=14),
        colorway=PALETTE,
    )
    return fig


def empty_notice():
    st.info("No transactions yet. Add one from **➕ Add Transaction**, "
            "or load demo data from **⚙️ Data tools** in the sidebar.")


# ---------------------------------------------------------------- pages
def page_dashboard(df, period, uid):
    hero("📊 Dashboard", f"Your money at a glance · {period}")

    if df.empty:
        empty_notice()
        return

    income, expense, balance, savings_pct = totals(df)

    row1 = st.columns(2)
    row2 = st.columns(2)
    with row1[0]:
        kpi("Total Income", money(income), "income", "💵")
    with row1[1]:
        kpi("Total Expenses", money(expense), "expense", "💸")
    with row2[0]:
        kpi("Remaining Balance", money(balance), "balance", "🏦")
    with row2[1]:
        kpi("Savings %", f"{savings_pct:.1f}%", "savings", "🐷")

    # Show budget progress only when one specific month is selected.
    if period != "All time":
        budget = db.get_budget(uid, period)
        if budget > 0:
            st.subheader("Budget")
            progress_bar(expense / budget)
            st.caption(f"{money(expense)} spent of {money(budget)}")

    st.subheader("Recent transactions")
    show_table(df.head(5))


def page_add(uid):
    hero("➕ Add Transaction", "Record income or an expense in seconds")

    # The type selector is OUTSIDE the form so the category list can change
    # immediately when you switch between Income and Expense.
    t_type = st.radio("Type", ["Income", "Expense"], horizontal=True)
    categories = db.INCOME_CATEGORIES if t_type == "Income" else db.EXPENSE_CATEGORIES

    with st.form("add_form", clear_on_submit=True):
        t_date = st.date_input("Date", value=date.today())
        category = st.selectbox("Category", categories)
        description = st.text_input("Description", max_chars=100,
                                    placeholder="e.g. October salary")
        amount = st.number_input(f"Amount ({CURRENCY})", min_value=0.0,
                                 max_value=1_000_000_000.0, step=100.0, format="%.2f")
        submitted = st.form_submit_button("💾 Save transaction")

    if submitted:
        # ---- validation ----
        errors = []
        if not description.strip():
            errors.append("Please enter a description.")
        if amount <= 0:
            errors.append("Amount must be greater than zero.")
        if errors:
            for message in errors:
                st.error(message)
            return
        # ---- save ----
        try:
            db.add_transaction(uid, t_date, description, category, t_type, amount)
            st.success(f"Saved {t_type.lower()} of {money(amount)} ({category}).")
        except sqlite3.Error as err:
            st.error(f"Could not save the transaction: {err}")


def page_analytics(df, df_all, period):
    hero("📈 Analytics", "See where your money comes from and where it goes")
    if df_all.empty:
        empty_notice()
        return

    # ----- monthly charts use ALL data so you can compare months -----
    monthly = df_all.groupby(["month", "type"], as_index=False)["amount"].sum()

    st.subheader("Income vs Expense (by month)")
    fig = px.bar(monthly, x="month", y="amount", color="type", barmode="group",
                 color_discrete_map=COLOR_MAP,
                 labels={"month": "Month", "amount": f"Amount ({CURRENCY})", "type": ""})
    fig.update_xaxes(type="category")
    st.plotly_chart(style_figure(fig))

    st.subheader("Monthly spending")
    spending = monthly[monthly["type"] == "Expense"]
    if spending.empty:
        st.info("No expenses recorded yet.")
    else:
        fig = px.line(spending, x="month", y="amount", markers=True,
                      labels={"month": "Month", "amount": f"Spent ({CURRENCY})"})
        fig.update_traces(line_color=EXPENSE_COLOR, line_width=4, marker_size=10,
                          fill="tozeroy", fillcolor="rgba(239,68,68,0.15)")
        fig.update_xaxes(type="category")
        st.plotly_chart(style_figure(fig))

    # ----- category charts follow the period chosen in the sidebar -----
    st.subheader(f"Spending by category ({period})")
    expenses = df[df["type"] == "Expense"]
    if expenses.empty:
        st.info("No expenses in this period.")
        return

    by_category = (expenses.groupby("category", as_index=False)["amount"].sum()
                   .sort_values("amount", ascending=False))
    top = by_category.iloc[0]
    st.metric("Highest spending category", top["category"], money(top["amount"]),
              delta_color="off")

    fig = px.pie(by_category, names="category", values="amount", hole=0.5,
                 color_discrete_sequence=PALETTE)
    fig.update_traces(textinfo="percent", textposition="inside")
    st.plotly_chart(style_figure(fig))


def page_budget(df_all, uid):
    hero("🎯 Monthly Budget", "Set a limit and stay on track")

    months = [db.month_start(i).strftime("%Y-%m") for i in range(12)]  # newest first
    month = st.selectbox("Month", months)

    current_budget = db.get_budget(uid, month)
    with st.form("budget_form"):
        new_budget = st.number_input(
            f"Budget for {month} ({CURRENCY})", min_value=0.0,
            max_value=1_000_000_000.0, step=500.0, format="%.2f",
            value=current_budget, key=f"budget_input_{month}",
        )
        saved = st.form_submit_button("💾 Save budget")

    if saved:
        try:
            db.set_budget(uid, month, new_budget)
            st.success(f"Budget for {month} set to {money(new_budget)}.")
            current_budget = new_budget
        except sqlite3.Error as err:
            st.error(f"Could not save the budget: {err}")

    # Amount spent this month
    if df_all.empty:
        spent = 0.0
    else:
        spent = df_all[(df_all["month"] == month) & (df_all["type"] == "Expense")]["amount"].sum()
    remaining = current_budget - spent

    c1, c2, c3 = st.columns(3)
    c1.metric("Budget", money(current_budget))
    c2.metric("Spent", money(spent))
    c3.metric("Remaining", money(remaining))

    if current_budget <= 0:
        st.info("No budget set for this month yet. Enter an amount above and save.")
        return

    used = spent / current_budget
    progress_bar(used)
    st.caption(f"{used * 100:.0f}% of the budget used")
    if used > 1:
        st.error(f"Over budget by {money(-remaining)}!")
    elif used >= 0.8:
        st.warning("You have used more than 80% of your budget.")
    else:
        st.success("You are within budget. Keep it up!")


def page_history(df, uid):
    hero("🧾 Transaction History", "Search, filter, export or delete entries")
    if df.empty:
        empty_notice()
        return

    # ----- filters -----
    f1, f2 = st.columns(2)
    types = f1.multiselect("Type", ["Income", "Expense"], default=["Income", "Expense"])
    cats = f2.multiselect("Category (empty = all)", sorted(df["category"].unique()))
    search = st.text_input("Search description")

    filtered = df[df["type"].isin(types)]
    if cats:
        filtered = filtered[filtered["category"].isin(cats)]
    if search.strip():
        filtered = filtered[filtered["description"].str.contains(search.strip(), case=False, regex=False)]

    st.caption(f"{len(filtered)} transaction(s)")
    view = show_table(filtered)

    st.download_button("⬇️ Download as CSV", data=view.to_csv(index=False).encode("utf-8"),
                       file_name="transactions.csv", mime="text/csv")

    # ----- delete -----
    with st.expander("🗑️ Delete a transaction"):
        if filtered.empty:
            st.write("Nothing to delete.")
        else:
            labels = {
                int(r.id): f"{r.date:%Y-%m-%d} | {r.description} | {r.category} | {money(r.amount)}"
                for r in filtered.itertuples()
            }
            chosen = st.selectbox("Choose a transaction", list(labels.keys()),
                                  format_func=lambda i: labels[i])
            if st.button("Delete selected"):
                try:
                    db.delete_transaction(uid, chosen)
                    st.toast("Transaction deleted.")
                    st.rerun()
                except sqlite3.Error as err:
                    st.error(f"Could not delete: {err}")



# ---------------------------------------------------------------- login
def login_screen():
    """Shown to visitors who are not logged in."""
    hero("💰 Personal Finance Tracker", "Track income, expenses and budgets. Your data is private to your account.")
    tab_login, tab_signup = st.tabs(["🔑 Login", "📝 Create account"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            go = st.form_submit_button("Login")
        if go:
            user = db.authenticate(username, password)
            if user:
                st.session_state["user"] = user
                st.rerun()
            else:
                st.error("Wrong username or password.")

    with tab_signup:
        with st.form("signup_form"):
            new_user = st.text_input("Choose a username", max_chars=30)
            pw1 = st.text_input("Choose a password (min 8 characters)", type="password")
            pw2 = st.text_input("Repeat password", type="password")
            create = st.form_submit_button("Create account")
        if create:
            if pw1 != pw2:
                st.error("The two passwords do not match.")
            else:
                try:
                    st.session_state["user"] = db.create_user(new_user, pw1)
                    st.rerun()
                except ValueError as err:
                    st.error(str(err))
                except sqlite3.Error as err:
                    st.error(f"Database error: {err}")


# ---------------------------------------------------------------- layout
if "user" not in st.session_state:
    login_screen()
    st.stop()  # nothing below runs until the user logs in

user = st.session_state["user"]
uid = user["id"]

df_all = db.get_transactions(uid)

st.sidebar.title("💰 Finance Tracker")
st.sidebar.write(f"👤 Signed in as **{user['username']}**")
if st.sidebar.button("Log out"):
    del st.session_state["user"]
    st.rerun()
page = st.sidebar.radio(
    "Go to",
    ["📊 Dashboard", "➕ Add Transaction", "📈 Analytics", "🎯 Budget", "🧾 History"],
)

# Period filter (used by Dashboard, Analytics categories and History)
month_options = ["All time"] + sorted(df_all["month"].unique(), reverse=True)
period = st.sidebar.selectbox("Period", month_options)
df = df_all if period == "All time" else df_all[df_all["month"] == period]

with st.sidebar.expander("⚙️ Data tools"):
    if st.button("Load sample data"):
        db.load_sample_data(uid)
        st.rerun()
    confirm = st.checkbox("I want to delete ALL my data (my account only)")
    if st.button("Clear all data", disabled=not confirm):
        db.clear_all_data(uid)
        st.rerun()

if page.endswith("Dashboard"):
    page_dashboard(df, period, uid)
elif page.endswith("Add Transaction"):
    page_add(uid)
elif page.endswith("Analytics"):
    page_analytics(df, df_all, period)
elif page.endswith("Budget"):
    page_budget(df_all, uid)
else:
    page_history(df, uid)
