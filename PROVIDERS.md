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

### Performance Comparison (Sequential)

| Provider | Model | Speed (sec/call) | 200-msg Simulation | Cost |
|----------|-------|------------------|-------------------|------|
| Cerebras | gpt-oss-120b | ~1.6 | ~5 minutes | External API |
| Buddy | GPT-OSS-120b | ~11.4 | ~38 minutes | UCO HPC (free) |
| Buddy | GPT-OSS-20b | ~49 | ~163 minutes | UCO HPC (free) |

## Parallel Processing for Tournament Runs

Buddy HPC supports parallel API calls, enabling multiple contestants to run simultaneously. Through extensive testing, we've determined the optimal batch size for tournament operations.

### Batch Size Performance (Tested March 2026)

| Batch Size | Total Time | Avg/Call | Speedup | 20 Contestants × 200 Messages |
|------------|-----------|----------|---------|-------------------------------|
| 3 parallel | 15.5s | 13.9s | 2.21x | 5.7 hours |
| 5 parallel | 29.2s | 23.0s | 1.95x | 6.5 hours |
| **6 parallel** ⭐ | **27.4s** | **20.0s** | **2.50x** | **5.1 hours** |
| 8 parallel | 37.8s | 25.0s | 2.41x | 5.2 hours |
| 12 parallel | 77.9s | 47.0s | 1.76x | 7.2 hours |

**Key Findings:**
- **Optimal batch size: 6 parallel calls**
- Best throughput: 0.22 calls/second
- GPT-OSS-120b (3 GPU) sweet spot is 6 concurrent requests
- Beyond 6 parallel, heavy queuing occurs with diminishing returns
- Batch size 3 shows high variance (11.6-22.9s)

### Tournament Run Strategy

For a tournament with 20 contestants running 200 messages each:

**Recommended: Batches of 6**
```bash
# Run 6 contestants in parallel (3.3 batches × 20 contestants)
# Total time: ~5.1 hours per tournament round
```

**Implementation:** Use a tournament runner script that spawns 6 simulator processes concurrently, waits for batch completion, then starts the next batch.

## Recommendations

- **Development/Testing**: Use `--model cerebras` for quick iterations (~5 min per 200-msg sim)
- **Tournament Runs**: Use `--model buddy` with **6 parallel batches** (~5.1 hours for 20 contestants)
- **Single Test Run**: Buddy sequential is fine (~38 minutes per contestant)
- **Cost Optimization**: Buddy eliminates all external API costs

## Troubleshooting

### Cerebras Not Working
- Check `CEREBRAS_API_KEY` is set in `.env`
- Verify API key is valid: `curl https://api.cerebras.ai/v1/models -H "Authorization: Bearer $CEREBRAS_API_KEY"`

### Buddy Not Working
- Check `BUDDY_API_KEY` is set in `.env`
- Verify API key is valid: `curl https://ai.hpc.uco.edu/api/models -H "Authorization: Bearer $BUDDY_API_KEY"`
- Check UCO HPC cluster is accessible

### Slow Performance
- Sequential Buddy calls take ~11-12 sec/call (expected)
- Parallel batches take ~20-30 sec/call depending on batch size (expected)
- Consider using Cerebras for development, Buddy for production
- Use batch size 6 for optimal tournament throughput

## Testing Performance

Test scripts are included to verify provider performance and optimal batch sizes:

### Basic Provider Test
```bash
python3 test_providers.py
```
Compares Cerebras vs Buddy sequential performance.

### Batch Size Optimization Test
```bash
python3 test_optimal_batch.py
```
Tests batch sizes 3, 5, 6, and 8 with 3 runs each. Takes ~5-10 minutes.

### Custom Parallel Test
```python
python3 test_parallel.py  # Tests 5 parallel calls
```

These tests help validate that the Buddy HPC cluster is performing as expected and can guide adjustments if the cluster configuration changes.
