# StorySpark ✨

AI-generated writing prompts to spark your life stories.

## About

StorySpark is a website that provides AI-generated prompts for writers to record stories and thoughts from their lives. The goal is to help people collect meaningful memories and experiences that could eventually become a book.

## Features

- 🎯 AI-generated writing prompts to inspire storytelling
- 📝 Blog section for recording story responses
- 🎨 Clean, modern, responsive design
- ♿ Accessible to all users
- 🌓 Dark/light mode support
- 📱 Mobile-friendly interface

## Automated AI Prompt Generation

StorySpark can now automatically generate new writing prompts using an Azure AI Foundry deployed model.

### Setup Azure AI Secrets

Add the following repository secrets in **GitHub → Settings → Secrets and variables → Actions**:

| Secret Name | Description |
|-------------|-------------|
| `AZURE_AI_ENDPOINT` | Endpoint of your Azure AI Foundry Inference resource (e.g. `https://my-ai-resource-xyz.inference.azure.com`) |
| `AZURE_AI_KEY` | API key for the resource |
| `AZURE_AI_MODEL` | Model or deployment name (e.g. `gpt-4o-mini`, `gpt-4o`, `phi-4`, etc.) |

### Generation Workflow

Scheduled and manual generation is handled by a workflow (`generate-prompts.yml`) that:
1. Installs dependencies (including `azure-ai-inference`).
2. Runs `scripts/generate_prompts.py` to request new prompts.
3. Commits changes to `docs/prompts.md` if any were generated.
4. The existing deployment workflow then publishes updates to Pages.

Markers in `docs/prompts.md`:
```html
<!-- AI-GENERATED-PROMPTS:START -->
<!-- AI-GENERATED-PROMPTS:END -->
```
Generated prompts are inserted between these markers under a dated heading.

### Run Locally

Create a `.env` file (optional) with:
```bash
AZURE_AI_ENDPOINT=your-endpoint
AZURE_AI_KEY=your-key
AZURE_AI_MODEL=gpt-4o-mini
```
Install dependencies and run:
```bash
pip install -r requirements.txt
python scripts/generate_prompts.py --count 5
```
Use `--dry-run` to preview without writing.

### Customizing Prompt Style

Adjust the system prompt logic in `scripts/generate_prompts.py` (`build_system_prompt()`) to change tone, focus areas, or formatting. Keep JSON contract intact for reliable parsing.

### Troubleshooting

- Empty output: Ensure model supports chat completions and secrets are correct.
- JSON parse error: Model may have added commentary—tune system prompt for stricter instructions.
- Duplicate prompts: Increase context window or include more existing prompts by removing the 4000-char trim.
- Authentication errors: Regenerate the Azure AI key or verify endpoint URL.

### Security Notes

- Secrets are never committed—only referenced in the workflow environment.
- Avoid echoing secrets in workflow logs.
- Restrict repository write access; the generation workflow commits to `main`.

### Extending Further

- Add a PR preview workflow to review generated prompts before merging.
- Run a link checker (`lychee`/`markdown-link-check`) after generation.
- Add moderation classification step to filter sensitive content.


## Local Development

### Prerequisites

- Python 3.12 or higher
- pip

### Setup

1. Clone the repository:
```bash
git clone https://github.com/codess-aus/StorySpark.git
cd StorySpark
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the development server:
```bash
mkdocs serve
```

4. Open your browser to `http://127.0.0.1:8000`

### Building the Site

To build the static site:
```bash
mkdocs build
```

The built site will be in the `site/` directory.

## Deployment

The site is automatically deployed to GitHub Pages when changes are pushed to the `main` branch.

Visit the live site at: https://codess-aus.github.io/StorySpark/

## Project Structure

```
StorySpark/
├── docs/                  # Documentation source files
│   ├── index.md          # Home page
│   ├── prompts.md        # Writing prompts page
│   ├── about.md          # About page
│   └── stories/          # Blog section
│       ├── index.md      # Stories index
│       ├── .authors.yml  # Blog authors
│       └── posts/        # Blog posts
├── .github/
│   └── workflows/
│       └── deploy.yml    # GitHub Pages deployment
├── mkdocs.yml            # MkDocs configuration
└── requirements.txt      # Python dependencies
```

## Contributing

Contributions are welcome! Feel free to:

- Submit new writing prompts
- Share your stories
- Improve the design or accessibility
- Fix bugs or add features

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Credits

Built with:
- [MkDocs](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)