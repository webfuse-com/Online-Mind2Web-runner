# Online-Mind2Web Runner

[Online-Mind2Web](https://huggingface.co/datasets/osunlp/Online-Mind2Web) [WebJudge](https://github.com/OSU-NLP-Group/Online-Mind2Web) evaluation runner. Works with any HTTP-based web agent that implements the `online-mind2web-v2` request-reponse schema. Wraps the original dataset (Hugging Face) and judge implementation (GitHub).

## Setup

``` console
./init.sh
```

Create a `.env` file (compare `.env.example`). Required definitions:

- `HF_TOKEN` – Hugging Face dataset access token.
- `JUDGE_API_KEY` – OpenAI API key (used by WebJudge).

## Run

> Run a mock agent to test the setup.
> 
> ``` console
>  python3 -m mock_agent
> ```

### 1. Run Agent on Dataset

``` console
python3 -m agent_runner --agent-url <URL> [--agent-key <KEY>] [--agent-timeout 600]
```

### 2. Run Judge on Agent Results

``` console
python3 -m judge_runner
```

### 3. Analyze Judge Results

``` console
python3 -m judge_analyze
```

## Web Agent Adapter

### Input (POST Request)

``` ts
interface Request.POST {
  "task_id": string,
  "task": string,
  "website": string,  // URL
  "reference_length": number
}
```

### Output (Response)

``` ts
// online-mind2web-v2
interface Response {
  "schema_version": "online-mind2web-v2",
  "task": string,
  "task_id": string,
  "reference_length": number,
  "agent_final_answer": string,
  "action_history": {
    "step": number,
    "screenshot": string,  // URL, data-URI, local path or Base64
    "url": string,
    "action": string,      // e.g., "button -> CLICK"
    "action_status"?: string,
    "thought": string
  }[]
}