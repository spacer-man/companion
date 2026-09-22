<div align="center">

# 🤝 Companion

**Your AI agent for staying organized, focused, and productive in everyday conversations.**

[![License](https://img.shields.io/github/license/spacer-man/companion)](LICENSE)
[![Type Check](https://github.com/spacer-man/companion/actions/workflows/ty.yml/badge.svg)](https://github.com/spacer-man/companion/actions/workflows/ty.yml)
[![Powered by OpenAI Agents SDK](https://img.shields.io/badge/Powered%20by-OpenAI%20Agents%20SDK-412991?logo=openai&logoColor=white)](https://github.com/openai/openai-agents-python)

</div>

---

## Overview

**Companion** is an AI agent designed to help you manage information and stay focused through natural conversations.

Currently, Companion works through **Telegram**, with support for MCP servers, knowledge management, audio transcription, and multi-message processing.

## Features

### 🧠 Knowledge & Tasks

* **Store important information** using MCP servers.
* **Search your knowledge base** using MCP.
* **Stay focused on important tasks** and keep relevant context available.

### 💬 Telegram

Companion currently uses [aiogram](https://github.com/aiogram/aiogram) as its Telegram interface.

* Rich Markdown messages and message drafting.
* Private one-to-one conversations.
* Audio message transcription using [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
* Processing multiple Telegram messages as a single agent turn.
* SOCKS proxy support for Telegram Bot API connections.

### 🔌 MCP & Agents

* Connect and work with **MCP servers**.
* Expose many agent tools through **three meta-tools**, reducing the tool-context overhead for local LLMs.
* Built around the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python).

### 🛠️ Telegram Formatting

Rich Telegram message formatting and message drafting are powered by [telegramify-markdown](https://github.com/sudoskys/telegramify-markdown).

## Roadmap

Companion currently supports **Telegram as its only interface**. Additional ways to interact with the agent may be added in the future.

Possible future interfaces include other messaging platforms and dedicated clients.

## License

See [LICENSE](LICENSE).
