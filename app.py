import os
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

APP_DIR = Path(__file__).parent
SEED_FILE = APP_DIR / "procurement_seed.csv"
DB_FILE = Path(os.getenv("PROCUREMENT_DB_PATH", APP_DIR / "procurement.db"))
COLUMNS = ["id", "status", "sno", "saree_type", "color", "cost_price", "selling_price", "profits", "final_price", "comments", "customer_details", "gst", "stock", "purchase_date"]
MONEY_COLUMNS = ["cost_price", "selling_price", "profits", "final_price"]

st.set_page_config(page_title="ReMa | Procurement", page_icon="🧵", layout="wide")
st.markdown("""
<style>
  .block-container {padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1450px;}
  [data-testid="stMetric"] {background: #f7f7f5; border: 1px solid #e8e7e2; padding: 15px 18px; border-radius: 12px;}
  div[data-testid="stMetricValue"] {font-size: 1.65rem;}
  .app-subtitle {color: #777; margin-top: -0.5rem;}
</style>
""", unsafe_allow_html=True)


def normalize_frame(df):
    df = df.copy()
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = None
    df = df[COLUMNS]
    for c in MONEY_COLUMNS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["id"] = pd.to_numeric(df["id"], errors="coerce")
    df["sno"] = df["sno"].fillna("").astype(str).replace("nan", "")
    for c in ["status", "saree_type", "color", "comments", "customer_details", "gst", "stock", "purchase_date"]:
        df[c] = df[c].fillna("").astype(str).replace("nan", "").str.strip()
    df["status"] = df["status"].apply(lambda s: "Sold" if s.lower() == "sold" else "In Stock")
    return df


def db_connect():
    con = sqlite3.connect(DB_FILE, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS procurement (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status TEXT NOT NULL DEFAULT 'In Stock', sno TEXT, saree_type TEXT NOT NULL,
        color TEXT, cost_price REAL, selling_price REAL, profits REAL, final_price REAL,
        comments TEXT, customer_details TEXT, gst TEXT, stock TEXT, purchase_date TEXT
    )""")
    con.commit()
    return con


def get_supabase():
    url = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL", ""))
    key = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY", ""))
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as exc:
        st.error(f"Could not initialize Supabase: {exc}")
        st.stop()


supabase = get_supabase()


def initialize_storage():
    seed = normalize_frame(pd.read_csv(SEED_FILE))
    if supabase:
        existing = supabase.table("procurement").select("id").limit(1).execute().data
        if not existing:
            rows = seed.drop(columns=["id"]).to_dict("records")
            # Keep the existing serial numbers, but let the database assign unique IDs.
            supabase.table("procurement").insert(rows).execute()
    else:
        con = db_connect()
        count = con.execute("SELECT COUNT(*) FROM procurement").fetchone()[0]
        if count == 0:
            seed = seed.drop(columns=["id"])
            seed.to_sql("procurement", con, if_exists="append", index=False)
        con.close()


def load_data():
    if supabase:
        rows = supabase.table("procurement").select("*").order("id").execute().data
        return normalize_frame(pd.DataFrame(rows, columns=COLUMNS)) if rows else pd.DataFrame(columns=COLUMNS)
    con = db_connect()
    df = pd.read_sql_query("SELECT * FROM procurement ORDER BY id", con)
    con.close()
    return normalize_frame(df)


def insert_record(record):
    record = {k: v for k, v in record.items() if k != "id"}
    for c in MONEY_COLUMNS:
        if record.get(c) in (None, ""):
            record[c] = None
        else:
            record[c] = float(record[c])
    if supabase:
        supabase.table("procurement").insert(record).execute()
    else:
        con = db_connect()
        fields = list(record.keys())
        placeholders = ",".join(["?"] * len(fields))
        con.execute(f"INSERT INTO procurement ({','.join(fields)}) VALUES ({placeholders})", [record[k] for k in fields])
        con.commit(); con.close()


def update_record(record_id, patch):
    for c in MONEY_COLUMNS:
        if c in patch:
            patch[c] = None if patch[c] in (None, "") else float(patch[c])
    if supabase:
        supabase.table("procurement").update(patch).eq("id", int(record_id)).execute()
    else:
        con = db_connect()
        fields = list(patch.keys())
        con.execute(f"UPDATE procurement SET {','.join([f'{f}=?' for f in fields])} WHERE id=?", [patch[k] for k in fields] + [int(record_id)])
        con.commit(); con.close()


def delete_record(record_id):
    if supabase:
        supabase.table("procurement").delete().eq("id", int(record_id)).execute()
    else:
        con = db_connect(); con.execute("DELETE FROM procurement WHERE id=?", (int(record_id),)); con.commit(); con.close()


def rupees(value):
    return "₹{:,.2f}".format(float(value or 0))


try:
    initialize_storage()
    data = load_data()
except Exception as exc:
    st.error("The procurement data store could not be opened. Check the database setup and try again.")
    st.exception(exc)
    st.stop()

if data.empty:
    data = pd.DataFrame(columns=COLUMNS)

# Financial values are derived from procurement records only.
data["effective_sale_price"] = data["final_price"].where(data["final_price"].notna(), data["selling_price"])
data["calculated_profit"] = data["effective_sale_price"] - data["cost_price"]
data["payment_status"] = data["comments"].str.strip().str.lower().apply(
    lambda x: "Not received" if "not received" in x else ("Received" if "received" in x else "Not specified")
)

with st.sidebar:
    st.markdown("# 🧵 ReMa")
    st.caption("Procurement & saree inventory")
    page = st.radio("Navigation", ["Dashboard", "Inventory", "Add procurement", "Update sale", "Export data"], label_visibility="collapsed")
    st.divider()
    st.caption("Data source: Procurement sheet only")
    if supabase:
        st.success("Cloud database connected")
    else:
        st.info("Local database mode")

st.title("Procurement & Inventory")
st.markdown('<p class="app-subtitle">Track saree purchases, stock, sales and customer payments in one place.</p>', unsafe_allow_html=True)

if page == "Dashboard":
    total_items = len(data)
    in_stock = data[data["status"] != "Sold"]
    sold = data[data["status"] == "Sold"]
    inventory_cost = in_stock["cost_price"].fillna(0).sum()
    sold_revenue = sold["effective_sale_price"].fillna(0).sum()
    sold_cost = sold["cost_price"].fillna(0).sum()
    sold_profit = (sold["effective_sale_price"].fillna(0) - sold["cost_price"].fillna(0)).sum()
    outstanding = sold[sold["payment_status"] == "Not received"]["effective_sale_price"].fillna(0).sum()

    a, b, c, d, e = st.columns(5)
    a.metric("Total sarees", f"{total_items:,}")
    b.metric("In stock", f"{len(in_stock):,}")
    c.metric("Stock cost value", rupees(inventory_cost))
    d.metric("Sales revenue", rupees(sold_revenue))
    e.metric("Sold gross profit", rupees(sold_profit))

    st.caption("Sales revenue and profit use Discount / Final Price when present; otherwise Selling Price. Profit is calculated as sale price minus cost price.")
    left, right = st.columns([1.15, 1])
    with left:
        st.subheader("Inventory by saree type")
        type_counts = in_stock.groupby("saree_type", dropna=False).size().reset_index(name="Items").sort_values("Items", ascending=False)
        if not type_counts.empty:
            fig = px.bar(type_counts, x="Items", y="saree_type", orientation="h", labels={"saree_type": "Saree type"}, text="Items")
            fig.update_layout(height=420, margin=dict(l=0, r=10, t=10, b=10), yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No inventory items yet.")
    with right:
        st.subheader("Stock status")
        status_df = pd.DataFrame({"Status": ["In stock", "Sold"], "Items": [len(in_stock), len(sold)]})
        if status_df["Items"].sum():
            fig = px.pie(status_df, names="Status", values="Items", hole=0.55)
            fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=10), legend_title_text="")
            st.plotly_chart(fig, use_container_width=True)
        st.metric("Pending customer payments", rupees(outstanding))
        unpaid_count = int((sold["payment_status"] == "Not received").sum())
        st.caption(f"{unpaid_count} sold item(s) marked Not Received in Comments.")

    st.subheader("Recently added / latest records")
    display = data.sort_values("id", ascending=False).head(8).copy()
    display = display.rename(columns={"saree_type":"Saree type", "cost_price":"Cost price", "selling_price":"Selling price", "final_price":"Final price", "customer_details":"Customer", "status":"Status"})
    st.dataframe(display[["id", "Status", "Saree type", "color", "Cost price", "Selling price", "Final price", "Customer"]], use_container_width=True, hide_index=True)

elif page == "Inventory":
    st.subheader("Inventory records")
    f1, f2, f3 = st.columns(3)
    status_filter = f1.selectbox("Status", ["All", "In Stock", "Sold"])
    type_options = ["All"] + sorted([x for x in data["saree_type"].dropna().unique().tolist() if x])
    type_filter = f2.selectbox("Saree type", type_options)
    search = f3.text_input("Search color / customer", placeholder="e.g. pink or Mani")
    view = data.copy()
    if status_filter != "All": view = view[view["status"] == status_filter]
    if type_filter != "All": view = view[view["saree_type"] == type_filter]
    if search.strip():
        term = search.strip().lower()
        view = view[view.apply(lambda r: term in " ".join(str(r[c]) for c in ["color", "customer_details", "saree_type", "comments"]).lower(), axis=1)]
    view = view.rename(columns={"id":"Record ID", "sno":"S.no", "status":"Status", "saree_type":"Saree type", "color":"Color", "cost_price":"Cost price", "selling_price":"Selling price", "profits":"Sheet profit", "final_price":"Final price", "comments":"Comments", "customer_details":"Customer", "gst":"GST", "stock":"Stock", "purchase_date":"Purchase date"})
    st.caption(f"Showing {len(view)} of {len(data)} procurement records")
    st.dataframe(view[["Record ID", "Status", "S.no", "Saree type", "Color", "Cost price", "Selling price", "Final price", "Sheet profit", "Comments", "Customer", "Stock"]], use_container_width=True, hide_index=True)
    with st.expander("Edit a record"):
        if not data.empty:
            chosen = st.selectbox("Select record ID", data["id"].astype(int).tolist(), key="edit_record_id")
            row = data[data["id"] == chosen].iloc[0]
            with st.form("edit_record_form"):
                new_status = st.selectbox("Status", ["In Stock", "Sold"], index=0 if row["status"] != "Sold" else 1)
                new_color = st.text_input("Color", row["color"])
                new_cost = st.number_input("Cost price (₹)", min_value=0.0, value=float(row["cost_price"] or 0), step=50.0)
                new_selling = st.number_input("Selling price (₹)", min_value=0.0, value=float(row["selling_price"] or 0), step=50.0)
                old_final = float(row["final_price"]) if pd.notna(row["final_price"]) else float(row["selling_price"] or 0)
                new_final = st.number_input("Final / discounted price (₹)", min_value=0.0, value=old_final, step=50.0)
                new_comments = st.selectbox("Payment / comments", ["", "Received", "Not Received", "Other"], index=["", "Received", "Not Received", "Other"].index(row["comments"] if row["comments"] in ["", "Received", "Not Received", "Other"] else "Other"))
                new_customer = st.text_input("Customer name", row["customer_details"])
                new_stock = st.text_input("Stock batch", row["stock"])
                submitted = st.form_submit_button("Save changes", type="primary")
            if submitted:
                patch = {"status": new_status, "color": new_color.strip(), "cost_price": new_cost, "selling_price": new_selling, "final_price": new_final, "profits": new_final-new_cost if new_status == "Sold" else row["profits"], "comments": new_comments, "customer_details": new_customer.strip(), "stock": new_stock.strip()}
                update_record(chosen, patch)
                st.success("Record updated.")
                st.rerun()

elif page == "Add procurement":
    st.subheader("Add a saree procurement record")
    st.write("Add each saree as a separate record. Leave sale and customer details blank until it is sold.")
    with st.form("add_procurement_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        saree_type = col1.text_input("Saree type *", placeholder="e.g. Tissue Silk")
        color = col2.text_input("Color *", placeholder="e.g. Peacock blue")
        cost = col1.number_input("Cost price (₹) *", min_value=0.0, step=50.0)
        stock = col2.text_input("Stock batch", placeholder="e.g. Stock 3")
        purchase_date = col1.date_input("Purchase date (optional)", value=None)
        gst = col2.text_input("GST / tax note", placeholder="Optional")
        selling = col1.number_input("Expected selling price (₹)", min_value=0.0, step=50.0)
        notes = col2.text_input("Notes")
        add = st.form_submit_button("Add to inventory", type="primary")
    if add:
        if not saree_type.strip() or not color.strip():
            st.error("Please enter both saree type and color.")
        else:
            next_sno = str(max(pd.to_numeric(data["sno"], errors="coerce").fillna(0).tolist() + [0]) + 1)
            insert_record({"status":"In Stock", "sno":next_sno, "saree_type":saree_type.strip(), "color":color.strip(), "cost_price":cost, "selling_price":selling or None, "profits":None, "final_price":None, "comments":notes.strip(), "customer_details":"", "gst":gst.strip(), "stock":stock.strip(), "purchase_date":str(purchase_date) if purchase_date else ""})
            st.success(f"Added {saree_type} — {color} to inventory.")
            st.rerun()

elif page == "Update sale":
    st.subheader("Record a sale")
    available = data[data["status"] != "Sold"]
    if available.empty:
        st.info("No in-stock items to mark as sold.")
    else:
        labels = {int(r.id): f"ID {int(r.id)} · {r.saree_type} · {r.color}" for r in available.itertuples()}
        with st.form("record_sale_form"):
            selected_id = st.selectbox("Saree sold", list(labels.keys()), format_func=lambda x: labels[x])
            selected = available[available["id"] == selected_id].iloc[0]
            st.caption(f"Cost price: {rupees(selected['cost_price'])}")
            sale_price = st.number_input("Final sale price (₹)", min_value=0.0, value=float(selected["selling_price"]) if pd.notna(selected["selling_price"]) else 0.0, step=50.0)
            customer = st.text_input("Customer name")
            payment = st.selectbox("Payment status", ["Received", "Not Received"])
            sale_notes = st.text_input("Sale notes (optional)")
            sold_submit = st.form_submit_button("Save sale", type="primary")
        if sold_submit:
            cost_price = float(selected["cost_price"]) if pd.notna(selected["cost_price"]) else 0.0
            comments = payment + (f"; {sale_notes.strip()}" if sale_notes.strip() else "")
            update_record(selected_id, {"status":"Sold", "final_price":sale_price, "profits":sale_price-cost_price, "customer_details":customer.strip(), "comments":comments})
            st.success(f"Sale recorded. Calculated gross profit: {rupees(sale_price-cost_price)}")
            st.rerun()

elif page == "Export data":
    st.subheader("Download procurement records")
    st.write("Exports only the Procurement records used by this app. No Balance Sheet data is included.")
    export = data[COLUMNS].copy()
    export = export.rename(columns={"id":"Record ID", "sno":"S.no", "status":"Status", "saree_type":"Saree type", "color":"Color", "cost_price":"Cost price", "selling_price":"Selling Price", "profits":"Profits", "final_price":"Discount/ Final Price", "comments":"Comments", "customer_details":"Customer Details", "gst":"GST", "stock":"Stock", "purchase_date":"Purchase Date"})
    st.download_button("Download CSV", export.to_csv(index=False).encode("utf-8-sig"), file_name="rema_procurement_export.csv", mime="text/csv", type="primary")
    st.caption("Keep a backup of exported records, especially if running this app on a hosting platform with ephemeral storage.")

st.divider()
st.caption("ReMa Procurement Tracker · Procurement sheet only · Verify financial totals against your records before using them for accounting or tax filing.")
