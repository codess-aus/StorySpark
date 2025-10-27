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