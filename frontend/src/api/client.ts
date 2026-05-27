const API_BASE_URL = "/api/v1";

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
};

type StreamRequestOptions<T> = RequestOptions & {
  onEvent: (event: T) => void;
};

export async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers: isFormData
      ? undefined
      : {
          "Content-Type": "application/json",
        },
    body:
      options.body === undefined
        ? undefined
        : isFormData
          ? (options.body as FormData)
          : JSON.stringify(options.body),
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const errorCode = data?.error?.code as string | undefined;
    const errorMessage =
      (data?.error?.message as string | undefined) || "请求失败，请稍后重试";
    throw new ApiError(errorMessage, response.status, errorCode);
  }

  return data as T;
}

function consumeSseBuffer<T>(
  buffer: string,
  onEvent: (event: T) => void
): { remaining: string } {
  let working = buffer;
  let separatorIndex = working.indexOf("\n\n");

  while (separatorIndex !== -1) {
    const rawBlock = working.slice(0, separatorIndex).trim();
    working = working.slice(separatorIndex + 2);

    if (rawBlock) {
      const lines = rawBlock.split(/\r?\n/);
      const dataLines = lines
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart());
      if (dataLines.length > 0) {
        onEvent(JSON.parse(dataLines.join("\n")) as T);
      }
    }

    separatorIndex = working.indexOf("\n\n");
  }

  return { remaining: working };
}

export async function requestEventStream<T>(
  path: string,
  options: StreamRequestOptions<T>
): Promise<void> {
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers: isFormData
      ? { Accept: "text/event-stream" }
      : {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
    body:
      options.body === undefined
        ? undefined
        : isFormData
          ? (options.body as FormData)
          : JSON.stringify(options.body),
  });

  if (!response.ok) {
    const text = await response.text();
    const data = text ? JSON.parse(text) : null;
    const errorCode = data?.error?.code as string | undefined;
    const errorMessage =
      (data?.error?.message as string | undefined) || "请求失败，请稍后重试";
    throw new ApiError(errorMessage, response.status, errorCode);
  }

  if (!response.body) {
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const consumed = consumeSseBuffer(buffer, options.onEvent);
    buffer = consumed.remaining;
    if (done) {
      if (buffer.trim()) {
        consumeSseBuffer(`${buffer}\n\n`, options.onEvent);
      }
      break;
    }
  }
}
