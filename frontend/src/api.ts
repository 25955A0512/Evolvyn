export function client(token: string) {
  const headers = (init: RequestInit) => ({
    Authorization: "Bearer " + token,
    "X-Requested-With": "Evolvyn",
    ...(sessionStorage.getItem("evolvyn-organization")
      ? { "X-Organization-Id": sessionStorage.getItem("evolvyn-organization")! }
      : {}),
    ...(!(init.body instanceof FormData)
      ? { "Content-Type": "application/json" }
      : {}),
    ...init.headers,
  });
  async function request(path: string, init: RequestInit = {}) {
    const response = await fetch("/api" + path, {
      ...init,
      headers: headers(init),
    });
    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Request failed" }));
      throw Error(
        typeof error.detail === "string" ? error.detail : "Invalid request",
      );
    }
    return response;
  }
  return {
    json: async (path: string, init: RequestInit = {}) =>
      (await request(path, init)).json(),
    async download(path: string, filename: string) {
      const blob = await (await request(path)).blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
    async watch(id: string, onRun: (run: any) => void, signal: AbortSignal) {
      const response = await request("/executions/" + id + "/live", { signal });
      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let end;
          while ((end = buffer.indexOf("\n\n")) >= 0) {
            const event = buffer.slice(0, end);
            buffer = buffer.slice(end + 2);
            if (event.startsWith("data: ")) onRun(JSON.parse(event.slice(6)));
          }
        }
      } finally {
        reader.releaseLock();
      }
    },
  };
}
