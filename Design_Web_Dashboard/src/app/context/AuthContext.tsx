import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';

const TOKEN_KEY = 'chattutor_token';
const USERNAME_KEY = 'chattutor_username';
const TOKEN_EXPIRES_AT_KEY = 'chattutor_token_expires_at';

interface AuthContextType {
  isAuthenticated: boolean;
  username: string | null;
  token: string | null;
  login: (username: string, password: string) => Promise<{ success: boolean; message: string }>;
  register: (username: string, password: string) => Promise<{ success: boolean; message: string }>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [username, setUsername] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(USERNAME_KEY);
  });

  const [token, setToken] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(TOKEN_KEY);
  });

  const [tokenExpiresAt, setTokenExpiresAt] = useState<number>(() => {
    if (typeof window === 'undefined') return 0;
    const expires = localStorage.getItem(TOKEN_EXPIRES_AT_KEY);
    return expires ? parseInt(expires, 10) : 0;
  });

  const [isLoading, setIsLoading] = useState(true);

  // 检查 token 是否过期
  const isTokenValid = () => {
    if (!token) return false;
    if (!tokenExpiresAt) return false;
    const now = Math.floor(Date.now() / 1000);
    if (now > tokenExpiresAt) {
      logout();
      return false;
    }
    return true;
  };

  useEffect(() => {
    // 初始化时检查 token 有效性
    if (token && !isTokenValid()) {
      logout();
    }
    setIsLoading(false);
  }, []);

  const login = async (username: string, password: string) => {
    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData,
      });

      if (response.status === 200) {
        const data = await response.json();
        setToken(data.access_token);
        setUsername(username);
        // 设置 token 过期时间（24 小时 = 86400 秒）
        const expiresAt = Math.floor(Date.now() / 1000) + (data.expires_in || 86400);
        setTokenExpiresAt(expiresAt);

        localStorage.setItem(TOKEN_KEY, data.access_token);
        localStorage.setItem(USERNAME_KEY, username);
        localStorage.setItem(TOKEN_EXPIRES_AT_KEY, expiresAt.toString());

        return { success: true, message: '登录成功!' };
      } else if (response.status === 401) {
        return { success: false, message: '用户名或密码错误' };
      } else {
        return { success: false, message: `登录失败：${response.status}` };
      }
    } catch (error) {
      if (error instanceof Error && error.name === 'TypeError') {
        return { success: false, message: '无法连接到服务器，请检查后端是否启动' };
      }
      return { success: false, message: `登录失败：${error}` };
    }
  };

  const register = async (username: string, password: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      if (response.status === 200) {
        const data = await response.json();
        setToken(data.access_token);
        setUsername(username);
        // 设置 token 过期时间（24 小时 = 86400 秒）
        const expiresAt = Math.floor(Date.now() / 1000) + (data.expires_in || 86400);
        setTokenExpiresAt(expiresAt);

        localStorage.setItem(TOKEN_KEY, data.access_token);
        localStorage.setItem(USERNAME_KEY, username);
        localStorage.setItem(TOKEN_EXPIRES_AT_KEY, expiresAt.toString());

        return { success: true, message: '注册成功!' };
      } else if (response.status === 400) {
        const errorData = await response.json();
        return { success: false, message: errorData.detail || '注册失败' };
      } else {
        return { success: false, message: `注册失败：${response.status}` };
      }
    } catch (error) {
      if (error instanceof Error && error.name === 'TypeError') {
        return { success: false, message: '无法连接到服务器，请检查后端是否启动' };
      }
      return { success: false, message: `注册失败：${error}` };
    }
  };

  const logout = () => {
    setToken(null);
    setUsername(null);
    setTokenExpiresAt(0);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USERNAME_KEY);
    localStorage.removeItem(TOKEN_EXPIRES_AT_KEY);
  };

  const value = {
    isAuthenticated: !!token && isTokenValid(),
    username,
    token,
    login,
    register,
    logout,
    isLoading,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
