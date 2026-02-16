#!/usr/bin/env node

import { FastMCP } from "fastmcp";
import { type } from "arktype";

const API_URL = process.env.JOB_API_URL || "http://localhost:8000/get-jobs";

const server = new FastMCP({
  name: "Job Searchoor",
  version: "0.1.0",
});

server.addTool({
  name: "get_jobs",
  description: "Get the available jobs",
  parameters: type({
    sinceWhen: type("/^[0-9]+[dw]$/").describe(
      "Since when to get available jobs. e.g., '1d' or '1w' (only days and weeks are supported)"
    ),
    "keywords?": type("string[]").describe("Keywords to filter jobs by"),
    "excludeKeywords?": type("string[]").describe(
      "Keywords to exclude from the jobs (if any of the results contains one of these keywords, it will be filtered out)"
    ),
    "isRemote?": type("boolean").describe(
      "Whether to filter jobs by remote work"
    ),
  }),
  execute: async (args) => {
    console.error(args);
    const response = await fetch(API_URL, {
      method: "POST",
      body: JSON.stringify({ ...args, limit: 10 }),
    });
    const data = (await response.json()) as { error: boolean; jobs: unknown[] };
    return {
      content: [{ type: "text", text: JSON.stringify(data.jobs) }],
    };
  },
});

server.start({ transportType: "stdio" });
