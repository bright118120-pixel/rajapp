"""
app.py - the Streamlit user interface for the Personal Finance Tracker.

Run with:  streamlit run app.py
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
    st.dataframe(
        view,
        hide_index=True,
        column_config={"Amount": st.column_config.NumberColumn(format=f"{CURRENCY}%.2f")},
    )
    return view


def style_figure(fig):
    """Make Plotly charts look good on small screens (legend below chart)."""
    fig.update_layout(
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", y=-0.2),
    )
    return fig


def empty_notice():
    st.info("No transactions yet. Add one from **➕ Add Transaction**, "
            "or load demo data from **⚙️ Data tools** in the sidebar.")


# ---------------------------------------------------------------- pages
def page_dashboard(df, period):
    st.header("📊 Dashboard")
    st.caption(f"Period: {period}")

    if df.empty:
        empty_notice()
        return

    income, expense, balance, savings_pct = totals(df)

    row1 = st.columns(2)
    row2 = st.columns(2)
    row1[0].metric("Total Income", money(income))
    row1[1].metric("Total Expenses", money(expense))
    row2[0].metric("Remaining Balance", money(balance))
    row2[1].metric("Savings %", f"{savings_pct:.1f}%")

    # Show budget progress only when one specific month is selected.
    if period != "All time":
        budget = db.get_budget(period)
        if budget > 0:
            st.subheader("Budget")
            st.progress(min(expense / budget, 1.0))
            st.caption(f"{money(expense)} spent of {money(budget)}")

    st.subheader("Recent transactions")
    show_table(df.head(5))


def page_add():
    st.header("➕ Add Transaction")

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
            db.add_transaction(t_date, description, category, t_type, amount)
            st.success(f"Saved {t_type.lower()} of {money(amount)} ({category}).")
        except sqlite3.Error as err:
            st.error(f"Could not save the transaction: {err}")


def page_analytics(df, df_all, period):
    st.header("📈 Analytics")
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
        fig.update_traces(line_color=EXPENSE_COLOR)
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

    fig = px.pie(by_category, names="category", values="amount", hole=0.45)
    st.plotly_chart(style_figure(fig))


def page_budget(df_all):
    st.header("🎯 Monthly Budget")

    months = [db.month_start(i).strftime("%Y-%m") for i in range(12)]  # newest first
    month = st.selectbox("Month", months)

    current_budget = db.get_budget(month)
    with st.form("budget_form"):
        new_budget = st.number_input(
            f"Budget for {month} ({CURRENCY})", min_value=0.0,
            max_value=1_000_000_000.0, step=500.0, format="%.2f",
            value=current_budget, key=f"budget_input_{month}",
        )
        saved = st.form_submit_button("💾 Save budget")

    if saved:
        try:
            db.set_budget(month, new_budget)
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
    st.progress(min(used, 1.0))
    st.caption(f"{used * 100:.0f}% of the budget used")
    if used > 1:
        st.error(f"Over budget by {money(-remaining)}!")
    elif used >= 0.8:
        st.warning("You have used more than 80% of your budget.")
    else:
        st.success("You are within budget. Keep it up!")


def page_history(df):
    st.header("🧾 Transaction History")
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
                    db.delete_transaction(chosen)
                    st.toast("Transaction deleted.")
                    st.rerun()
                except sqlite3.Error as err:
                    st.error(f"Could not delete: {err}")


# ---------------------------------------------------------------- layout
df_all = db.get_transactions()

st.sidebar.title("💰 Finance Tracker")
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
        db.load_sample_data()
        st.rerun()
    confirm = st.checkbox("I want to delete ALL my data")
    if st.button("Clear all data", disabled=not confirm):
        db.clear_all_data()
        st.rerun()

if page.endswith("Dashboard"):
    page_dashboard(df, period)
elif page.endswith("Add Transaction"):
    page_add()
elif page.endswith("Analytics"):
    page_analytics(df, df_all, period)
elif page.endswith("Budget"):
    page_budget(df_all)
else:
    page_history(df)
