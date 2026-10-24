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
      throw Object.assign(
        Error(
          typeof error.detail === "string" ? error.detail : "Invalid request",
        ),
        { status: response.status },
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
      let latest: any = null,
        failures = 0;
      const completed = () =>
        latest && !["CREATED", "RUNNING"].includes(latest.state);
      const delay = (ms: number) =>
        new Promise<void>((resolve, reject) => {
          const abort = () => {
            clearTimeout(timer);
            reject(new DOMException("Aborted", "AbortError"));
          };
          const timer = setTimeout(() => {
            signal.removeEventListener("abort", abort);
            resolve();
          }, ms);
          if (signal.aborted) abort();
          else signal.addEventListener("abort", abort, { once: true });
        });
      while (!signal.aborted) {
        try {
          const response = await request("/executions/" + id + "/live", {
            signal,
          });
          if (!response.body) throw Error("Live stream unavailable");
          const reader = response.body.getReader(),
            decoder = new TextDecoder();
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
                if (event.startsWith("data: ")) {
                  latest = JSON.parse(event.slice(6));
                  onRun(latest);
                }
              }
            }
          } finally {
            reader.releaseLock();
          }
          if (completed()) return;
          if (!latest) throw Error("No live state received");
          failures = 0;
        } catch (e: any) {
          if (signal.aborted || e.name === "AbortError") throw e;
          if ([401, 403, 404].includes(e.status) || ++failures >= 6)
            throw Error(
              "Live updates disconnected. Refresh the run status to reconnect.",
            );
          try {
            latest = await (
              await request("/executions/" + id, { signal })
            ).json();
            onRun(latest);
            if (completed()) return;
          } catch (snapshotError: any) {
            if (signal.aborted) throw snapshotError;
          }
        }
        await delay(Math.min(5000, 500 * 2 ** failures));
      }
    },
  };
}
