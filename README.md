# 🤖 Autonomous AI Browser Agent

An advanced, self-healing browser automation agent powered by **LangGraph**, **Playwright**, and **Claude 3.5 Sonnet**. This agent can plan tasks, write Playwright code, execute it, visually monitor for regressions, and self-heal when things go wrong.

## ✨ Key Features

- **🧠 Autonomous Planning**: Breaks down complex user requests (e.g., "Buy a blue t-shirt on Amazon") into executable steps.
- **🛡️ Self-Healing**: Detects execution errors (timeouts, missing elements) and uses **Vision (screenshots)** to diagnose and fix scripts automatically.
- **👁️ Visual Regression Monitor**: Compares execution steps against baseline screenshots to detect visual changes.
- **🎥 Video Recording**: Automatically records full sessions for debugging and audit.
- **🧭 Flow Discovery**: Can explore a website to identify and map critical user flows.
- **⚡ Robust Automation**: Handles new tabs, dynamic content, and anti-bot measures (like case-insensitive selectors).

## 📂 Project Structure

```
browser_agent/
├── app/
│   ├── agents/
│   │   ├── planner.py      # Decomposes tasks into steps
│   │   ├── coder.py        # Generates Playwright code for steps
│   │   ├── healer.py       # Fixes broken scripts using error logs & vision
│   │   ├── monitor.py      # Checks visual consistency vs baselines
│   │   └── discovery.py    # Explores sites to find user flows
│   ├── tools/
│   │   └── browser.py      # BrowserManager (Playwright wrapper)
│   ├── config.py           # LLM configuration (OpenRouter)
│   ├── graph.py            # LangGraph state machine definition
│   └── state.py            # Shared agent state schema
├── tests/
│   └── test_agent_flow.py  # Automated verification test suite
├── baselines/              # Visual regression baselines (auto-generated)
├── streamlit_app.py        # Web UI for the agent
├── requirements.txt        # Python dependencies
└── .env                    # Deployment secrets
```

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- An [OpenRouter](https://openrouter.ai/) API Key (with access to `anthropic/claude-3.5-sonnet`)

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository_url>
   cd browser_agent
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\Activate.ps1
   # Mac/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers**:
   ```bash
   playwright install
   ```

5. **Configure Environment**:
   Create a `.env` file in the root directory:
   ```ini
   OPENROUTER_API_KEY=sk-or-your-key-here
   ```

## 🎮 Usage

### Running the Web UI

The easiest way to interact with the agent is via the Streamlit interface:

```bash
streamlit run streamlit_app.py
```

- Enter your task in the chat input (e.g., *"Go to amazon.in and search for a laptop"*).
- Watch the agent step through the process in real-time.
- View execution logs and screenshots of any errors.

### Running Automated Tests

To verify the agent's core functionality (login flow, visual monitoring):

```bash
python tests/test_agent_flow.py
```

## 🏗️ Architecture

The agent is built as a **State Graph** using LangGraph:

1.  **Planner**: Receives the user goal and outputs a step-by-step plan.
2.  **Executor (Coder)**: Takes the current step and writes Playwright Python code to execute it.
3.  **Monitor**: After execution, compares the current page screenshot with a saved baseline for that step.
4.  **Healer**: If execution fails (exception) or visual regression is high, it analyzes the error + screenshot and rewrites the code.
5.  **Loop**: The graph continues until all steps are complete or max retries are reached.

## 🛠️ Troubleshooting

- **Error 402 (OpenRouter)**: The agent uses Vision and can be token-hungry. If you hit limits, check your OpenRouter credits. The agent is optimized to resize images to 1024px to save tokens.
- **Browser Closes Too Fast**: In the test script, press `Enter` in the terminal to close the browser after the test completes.
- **Logs**: Check `agent.log` for detailed backend execution logs.
