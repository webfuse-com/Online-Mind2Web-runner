# Online-Mind2Web Runner

Runs the original _Online-Mind2Web_ _WebJudge_ evaluator on any web agent exposed via HTTP(S).

## Setup

``` console
./init.sh
```

Create a `.env` file (compare `.env.example`). Required definitions:

- `HF_TOKEN` – _Hugging Face_ dataset access token.
- `AGENT_URL` – the evaluation target agent's HTTP(S) endpoint.
- `JUDGE_API_KEY` – _OpenAI_ API key (used by _WebJudge_).

## Run

``` console
python3 -m eval
```

> Run a mock agent to test the setup.
> 
> ``` console
>  python3 -m mock_agent
> ```

By default, results are collected in `eval_result/` (upstream JSONL, one line per task with `predicted_label`) and `trajectories/<task_id>/` (the submission package sent to the judge: `result.json` and `trajectory/*.png`).

## Web Agent Adapter

``` ts
interface Request.POST {
  "task_id": string,
  "task": string,
  "website": string,        // URL
  "reference_length": number
}
```

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
    "screenshot": string,   // URL, data-URI, local path or Base64
    "url": string,
    "action": string,       // e.g., "button -> CLICK"
    "action_status"?: string,
    "thought": string
  }[]
}