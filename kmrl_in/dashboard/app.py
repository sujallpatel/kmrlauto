import time
import requests
import streamlit as st
import pandas as pd

API_URL = "http://localhost:8000/api"

st.set_page_config(
    page_title="KMRL Intelligent Load Balancer Dashboard",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ KMRL Intelligent Document Load Balancer")
st.markdown("Real-time monitoring of predicted workload routing, priority queues, worker metrics & circuit breaker states.")

def fetch_metrics():
    try:
        res = requests.get(f"{API_URL}/metrics")
        return res.json() if res.status_code == 200 else {}
    except Exception:
        return {}

def fetch_workers():
    try:
        res = requests.get(f"{API_URL}/workers")
        return res.json() if res.status_code == 200 else []
    except Exception:
        return []

def fetch_tasks():
    try:
        res = requests.get(f"{API_URL}/tasks")
        return res.json() if res.status_code == 200 else []
    except Exception:
        return []

def fetch_dlq():
    try:
        res = requests.get(f"{API_URL}/dead-letter-queue")
        return res.json() if res.status_code == 200 else []
    except Exception:
        return []

# Sidebar Controls
st.sidebar.header("System Controls")
auto_refresh = st.sidebar.checkbox("Auto Refresh (3s)", value=False)
if auto_refresh:
    time.sleep(3)
    st.rerun()

metrics = fetch_metrics()
workers = fetch_workers()
tasks = fetch_tasks()
dlq = fetch_dlq()

# Metric Summary Cards
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Healthy Workers", f"{metrics.get('workers_healthy', 0)} / {metrics.get('workers_total', 0)}")
col2.metric("Queue Depth", metrics.get("queued_tasks", 0))
col3.metric("Processing Tasks", metrics.get("processing_tasks", 0))
col4.metric("Completed Docs", metrics.get("completed_documents", 0))
col5.metric("Dead Letter Queue", metrics.get("dead_letter_tasks", 0))
col6.metric("Avg Processing Time", f"{metrics.get('average_processing_time_sec', 0)} s")

st.divider()

# Worker Health & Utilization Section
st.subheader("🖥️ Worker Status & Resource Utilization")
if workers:
    w_cols = st.columns(len(workers))
    for idx, w in enumerate(workers):
        with w_cols[idx]:
            status_color = "🟢" if w["status"] == "HEALTHY" else ("🟡" if w["status"] == "DEGRADED" else "🔴")
            st.markdown(f"### {status_color} {w['worker_id']}")
            st.caption(f"Host: {w['hostname']} | State: **{w['status']}** | Circuit: **{w['circuit_status']}**")
            
            st.progress(w['cpu_usage'] / 100.0, text=f"CPU: {w['cpu_usage']}%")
            st.progress(w['memory_usage'] / 100.0, text=f"RAM: {w['memory_usage']}%")
            
            st.write(f"• Active Tasks: **{w['active_tasks']}**")
            st.write(f"• Queue Length: **{w['queue_length']}**")
            st.write(f"• Avg Exec Time: **{w['average_processing_time']}s**")
            st.write(f"• Capabilities: `{', '.join(w['supported_languages'])}`")
else:
    st.info("No workers registered yet or backend API is unreachable.")

st.divider()

# Document Task Routing Table & Dead Letter Queue Tabs
tab1, tab2, tab3 = st.tabs(["📋 Active Priority Task Queue", "💀 Dead Letter Queue (DLQ)", "🧪 Upload Test Document"])

with tab1:
    if tasks:
        df_tasks = pd.DataFrame(tasks)
        st.dataframe(
            df_tasks[["id", "document_id", "task_type", "assigned_worker", "status", "base_priority", "effective_priority", "predicted_workload", "combined_score"]],
            use_container_width=True
        )
    else:
        st.info("Task queue is currently empty.")

with tab2:
    if dlq:
        st.error(f"{len(dlq)} Tasks in Dead Letter Queue require attention!")
        df_dlq = pd.DataFrame(dlq)
        st.dataframe(df_dlq, use_container_width=True)
        
        task_to_retry = st.number_input("Enter Task ID to Retry", min_value=1, step=1)
        if st.button("Re-queue Task"):
            try:
                res = requests.post(f"{API_URL}/tasks/{task_to_retry}/retry")
                st.success(res.json().get("message", "Task re-queued"))
                st.rerun()
            except Exception as e:
                st.error(f"Error re-queuing task: {e}")
    else:
        st.success("Dead Letter Queue is empty. No failed tasks.")

with tab3:
    st.markdown("### Simulate Document Upload")
    with st.form("upload_form"):
        uploaded_file = st.file_uploader("Choose PDF or Image File")
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            safety = st.slider("Safety Criticality", 0, 100, 50)
            regulatory = st.slider("Regulatory Urgency", 0, 100, 30)
            language = st.selectbox("Language", ["English", "Malayalam", "Mixed"])
        with f_col2:
            business = st.slider("Business Importance", 0, 100, 40)
            deadline = st.slider("Deadline Urgency", 0, 100, 20)
            doc_type = st.selectbox("Document Type", ["Engineering", "Safety", "Regulatory", "Reference"])
            
        submitted = st.form_submit_button("Route & Submit Document")
        if submitted and uploaded_file:
            files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
            data = {
                "safety_criticality": safety,
                "regulatory_importance": regulatory,
                "business_importance": business,
                "deadline_urgency": deadline,
                "language": language,
                "document_type": doc_type
            }
            try:
                res = requests.post(f"{API_URL}/documents/upload", files=files, data=data)
                if res.status_code == 200:
                    out = res.json()
                    st.success(f"Routed to **{out['assigned_worker']}** with Task Score **{out['priority']['combined_task_score']}**!")
                    st.json(out)
                else:
                    st.error(f"Upload failed: {res.text}")
            except Exception as e:
                st.error(f"Failed to connect to API: {e}")
