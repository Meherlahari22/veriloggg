import os
import subprocess
import traceback
import streamlit as st

from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

st.set_page_config(
    page_title="Verilog AI Agent",
    page_icon="⚡",
    layout="wide"
)

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error("GEMINI_API_KEY not found. Please set it as an environment variable.")
    st.stop()

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    google_api_key=api_key,
    temperature=0
)

def clean_code(code):
    code = str(code)
    code = code.replace("```verilog", "")
    code = code.replace("```systemverilog", "")
    code = code.replace("```", "")
    return code.strip()

@tool
def generate_verilog_code(task_description: str) -> str:
    """Generate synthesizable Verilog-2001 RTL."""
    prompt = f"""
You are an expert RTL Verilog engineer.

Generate synthesizable Verilog-2001 code for:
{task_description}

Requirements:
1. Use Verilog-2001 syntax.
2. Make the design synthesizable.
3. Use a meaningful module name.
4. Include correct input and output declarations.
5. Do not generate a testbench.
6. Return ONLY Verilog code.
7. Do not use Markdown code fences.
"""
    response = llm.invoke(prompt)
    content = response.content
    if isinstance(content, list):
        content = "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        )
    return clean_code(content)

@tool
def generate_verilog_testbench(task_description: str, verilog_code: str) -> str:
    """Generate a Verilog testbench."""
    prompt = f"""
You are an expert Verilog verification engineer.

Hardware requirement:
{task_description}

RTL code:
{verilog_code}

Create a complete Verilog-2001 testbench.

Requirements:
1. Instantiate the DUT correctly.
2. Generate all required inputs.
3. Test normal cases.
4. Test edge cases.
5. Use $display statements.
6. End simulation using $finish.
7. Do not use SystemVerilog-only syntax.
8. Return ONLY testbench code.
9. Do not use Markdown code fences.
"""
    response = llm.invoke(prompt)
    content = response.content
    if isinstance(content, list):
        content = "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        )
    return clean_code(content)

def simulate_verilog(verilog_code, testbench_code):
    """Compile and simulate Verilog using Icarus Verilog."""
    try:
        verilog_code = clean_code(verilog_code)
        testbench_code = clean_code(testbench_code)

        with open("design.v", "w") as f:
            f.write(verilog_code)

        with open("testbench.v", "w") as f:
            f.write(testbench_code)

        compile_process = subprocess.run(
            ["iverilog", "-o", "simulation.out", "design.v", "testbench.v"],
            capture_output=True,
            text=True
        )

        if compile_process.returncode != 0:
            return {"status": "FAIL", "output": compile_process.stderr}

        simulation_process = subprocess.run(
            ["vvp", "simulation.out"],
            capture_output=True,
            text=True
        )

        output = simulation_process.stdout
        if simulation_process.stderr:
            output += "\n" + simulation_process.stderr

        return {
            "status": "PASS" if simulation_process.returncode == 0 else "FAIL",
            "output": output
        }

    except Exception:
        return {"status": "ERROR", "output": traceback.format_exc()}

def generate_report(task, verilog_code, testbench_code, simulation_result):
    """Generate final verification report."""
    prompt = f"""
You are a senior Verilog verification engineer.

Hardware requirement:
{task}

Generated RTL:
{verilog_code}

Generated testbench:
{testbench_code}

Simulation status:
{simulation_result["status"]}

Simulation output:
{simulation_result["output"]}

Prepare a concise verification report.

Include:
1. Design summary
2. RTL generation status
3. Testbench status
4. Compilation status
5. Simulation status
6. Test result
7. Errors if any
8. Final PASS or FAIL

Return the report in plain text.
"""
    response = llm.invoke(prompt)
    content = response.content
    if isinstance(content, list):
        content = "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content)

st.title("⚡ Verilog AI Agent")
st.write(
    "Generate Verilog RTL, automatically create a testbench, "
    "compile and simulate it using Icarus Verilog, and generate "
    "a verification report."
)

with st.sidebar:
    st.header("Agent Pipeline")
    st.write("1. 🧠 Verilog Developer")
    st.write("2. 🧪 Testbench Generator")
    st.write("3. ⚙️ Icarus Verilog Simulator")
    st.write("4. 📊 Verification Report")

task = st.text_area(
    "Enter your Verilog hardware requirement:",
    placeholder="Example: Design a 4-bit up counter with synchronous reset.",
    height=150
)

if st.button("🚀 Generate & Simulate", type="primary"):
    if not task.strip():
        st.warning("Please enter a Verilog hardware requirement.")
    else:
        with st.spinner("Generating Verilog RTL..."):
            try:
                verilog_code = generate_verilog_code.invoke(task)
            except Exception as e:
                st.error(f"Verilog generation failed:\n{e}")
                st.stop()

        st.subheader("1️⃣ Generated Verilog RTL")
        st.code(verilog_code, language="verilog")

        with st.spinner("Generating testbench..."):
            try:
                testbench_code = generate_verilog_testbench.invoke({
                    "task_description": task,
                    "verilog_code": verilog_code
                })
            except Exception as e:
                st.error(f"Testbench generation failed:\n{e}")
                st.stop()

        st.subheader("2️⃣ Generated Testbench")
        st.code(testbench_code, language="verilog")

        with st.spinner("Compiling and simulating with Icarus Verilog..."):
            simulation_result = simulate_verilog(verilog_code, testbench_code)

        st.subheader("3️⃣ Simulation Result")

        if simulation_result["status"] == "PASS":
            st.success("Compilation and simulation successful!")
        elif simulation_result["status"] == "FAIL":
            st.error("Compilation or simulation failed.")
        else:
            st.warning("Simulation encountered an error.")

        st.code(simulation_result["output"])

        with st.spinner("Generating verification report..."):
            try:
                report = generate_report(
                    task,
                    verilog_code,
                    testbench_code,
                    simulation_result
                )
            except Exception as e:
                report = f"Report generation failed:\n{e}"

        st.subheader("4️⃣ Verification Report")
        st.markdown(report)

        st.download_button(
            label="⬇️ Download Verilog RTL",
            data=verilog_code,
            file_name="design.v",
            mime="text/plain"
        )

        st.download_button(
            label="⬇️ Download Testbench",
            data=testbench_code,
            file_name="testbench.v",
            mime="text/plain"
        )

        st.success("Verilog Agent workflow completed!")
