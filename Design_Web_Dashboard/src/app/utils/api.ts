/**
 * API 客户端工具函数
 * 自动在请求中附加 JWT token
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';

const TOKEN_KEY = 'chattutor_token';

/**
 * 获取存储的 JWT token
 */
function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

/**
 * API 请求选项接口
 */
interface ApiRequestOptions extends RequestInit {
  requiresAuth?: boolean;
}

/**
 * 通用的 API 请求函数
 * 自动附加 JWT token（当 requiresAuth 为 true 时）
 */
export async function apiRequest<T>(
  endpoint: string,
  options: ApiRequestOptions = {}
): Promise<{ data?: T; error?: string; status?: number }> {
  const { requiresAuth = true, headers = {}, ...restOptions } = options;

  // 构建请求头
  const requestHeaders: HeadersInit = {
    'Content-Type': 'application/json',
    ...headers,
  };

  // 如果需要认证，附加 JWT token
  if (requiresAuth) {
    const token = getToken();
    if (token) {
      requestHeaders['Authorization'] = `Bearer ${token}`;
    }
  }

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...restOptions,
      headers: requestHeaders,
    });

    // 处理 401 未授权（token 过期或无效）
    if (response.status === 401) {
      // 清除本地存储的 token
      localStorage.removeItem(TOKEN_KEY);
      // 可以选择跳转到登录页
      window.location.href = '/login';
      return { error: '登录已过期，请重新登录', status: response.status };
    }

    // 处理 429 限流
    if (response.status === 429) {
      return { error: '请求太频繁，请稍后再试', status: response.status };
    }

    // 解析响应
    const data = await response.json();

    if (!response.ok) {
      return {
        error: data.detail || data.message || `请求失败：${response.status}`,
        status: response.status
      };
    }

    return { data, status: response.status };
  } catch (error) {
    // 网络错误
    if (error instanceof Error && error.name === 'TypeError') {
      return { error: '无法连接到服务器，请检查后端是否启动' };
    }
    return { error: `请求失败：${error}` };
  }
}

/**
 * 简化的 GET 请求
 */
export async function apiGet<T>(endpoint: string, requiresAuth = true) {
  return apiRequest<T>(endpoint, { method: 'GET', requiresAuth });
}

/**
 * 简化的 POST 请求
 */
export async function apiPost<T>(
  endpoint: string,
  body: unknown,
  requiresAuth = true
) {
  return apiRequest<T>(endpoint, {
    method: 'POST',
    body: JSON.stringify(body),
    requiresAuth,
  });
}

/**
 * 简化的 PUT 请求
 */
export async function apiPut<T>(
  endpoint: string,
  body: unknown,
  requiresAuth = true
) {
  return apiRequest<T>(endpoint, {
    method: 'PUT',
    body: JSON.stringify(body),
    requiresAuth,
  });
}

/**
 * 简化的 DELETE 请求
 */
export async function apiDelete<T>(endpoint: string, requiresAuth = true) {
  return apiRequest<T>(endpoint, { method: 'DELETE', requiresAuth });
}

export { API_BASE_URL };
