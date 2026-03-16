# LLM Provider Configuration

The VendingBench simulator supports multiple LLM providers. You can easily switch between them using the `--model` flag.

## Available Providers

### Cerebras (Fast, External API)
- **Speed**: ~2 seconds per API call
- **Cost**: External API usage charges
- **Use case**: Rapid development, quick testing iterations
- **Models**: `gpt-oss-120b` (120B parameters)

### Buddy HPC (Slower, UCO-Hosted)
- **Speed**: ~23 seconds per API call
- **Cost**: No external API costs (runs on UCO infrastructure)
- **Use case**: Official tournament runs, overnight simulations
- **Models**:
  - `GPT-OSS-120b` (120B, 3 GPUs, recommended)
  - `GPT-OSS-20b` (20B, 1 GPU, even slower ~49 sec)
  - `Command-R` (32B, 2 GPUs, RAG-specialized)
  - `Qwen3-Coder-Next` (80B, 3 GPUs, code-specialized)

## Switching Between Providers

### Quick Start

**Use Cerebras (fast):**
```bash
python3 run_sim.py --model cerebras --max-messages 200
```

**Use Buddy (slower, no cost):**
```bash
python3 run_sim.py --model buddy --max-messages 200
```

### Detailed Options

**Cerebras shortcuts:**
- `--model cerebras` (uses gpt-oss-120b)
- `--model cerebras-gpt-oss-120b`

**Buddy shortcuts:**
- `--model buddy` (uses GPT-OSS-120b)
- `--model buddy-gpt-oss-120b`
- `--model buddy-gpt-oss-20b`
- `--model buddy-command-r`
- `--model buddy-qwen3-coder`

### Default Provider

The default is currently set to **Buddy** (`buddy/GPT-OSS-120b`) in `model_client.py:443`.

To change the default, edit this line:
```python
def call_model(
    prompt: str,
    model_type: str = "buddy/GPT-OSS-120b",  # Change this line
    system_prompt: str = "",
    tools: list = None,
):
```

## Configuration Files

### Environment Variables

Both API keys must be set in `.env`:

```bash
# LLM Provider Options (use --model flag to choose between them)
CEREBRAS_API_KEY=csk-...  # Fast (~2 sec/call), external API
BUDDY_API_KEY=sk-...      # Slower (~23 sec/call), UCO HPC, no external costs
```

### Performance Comparison

| Provider | Model | Speed (sec/call) | 200-msg Simulation | Cost |
|----------|-------|------------------|-------------------|------|
| Cerebras | gpt-oss-120b | ~2 | ~7 minutes | External API |
| Buddy | GPT-OSS-120b | ~23 | ~77 minutes | UCO HPC (free) |
| Buddy | GPT-OSS-20b | ~49 | ~163 minutes | UCO HPC (free) |

## Recommendations

- **Development/Testing**: Use `--model cerebras` for quick iterations
- **Tournament Runs**: Use `--model buddy` for official simulations (no external costs)
- **Overnight Runs**: Buddy's slower speed is acceptable for scheduled tournament batches
- **Cost Optimization**: Use Cerebras only when speed is critical

## Troubleshooting

### Cerebras Not Working
- Check `CEREBRAS_API_KEY` is set in `.env`
- Verify API key is valid: `curl https://api.cerebras.ai/v1/models -H "Authorization: Bearer $CEREBRAS_API_KEY"`

### Buddy Not Working
- Check `BUDDY_API_KEY` is set in `.env`
- Verify API key is valid: `curl https://ai.hpc.uco.edu/api/models -H "Authorization: Bearer $BUDDY_API_KEY"`
- Check UCO HPC cluster is accessible

### Slow Performance
- This is expected with Buddy (23 sec/call)
- Consider using Cerebras for development, Buddy for production
- Plan for overnight execution for tournament runs
