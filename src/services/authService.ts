import { ref} from 'vue'
import axios from 'axios'

// Types
export interface User {
  id: number
  userName: string
  loginName: string
  defaultRole: string
  email?: string
  mobileNo?: string
  phoneNo?: string
  remark?: string
}

export interface LoginCredentials {
  username: string
  password: string
}

export interface AuthResponse {
  success: boolean
  user?: User
  permissions?: string[]
  message?: string
  error?: string
}

// State
export const authenticated = ref(false)
export const validUser = ref(false)
export const user = ref<User | null>(null)
export const userPermissions = ref<string[]>([])
export const error = ref<string | null>(null)
export const loading = ref(false)
export const authInitialized = ref(false)
let initPromise: Promise<void> | null = null
// API Configuration
const API_BASE_URL = '/api'

// Authentication Functions
export async function login(credentials: LoginCredentials): Promise<AuthResponse> {
  loading.value = true
  error.value = null

  try {
    // Validate against AD/LDAP with detailed error messages
    const ldapResponse = await axios.post(`${API_BASE_URL}/validate-ldap-user`, {
      username: credentials.username,
      password: credentials.password
    })

    if (ldapResponse.data.status === 'error') {
      // Return specific error based on error type
      const errorType = ldapResponse.data.error_type
      let errorMessage = 'Authentication failed'

      if (errorType === 'invalid_username') {
        errorMessage = 'Invalid username'
      } else if (errorType === 'invalid_password') {
        errorMessage = 'Invalid password'
      } else {
        errorMessage = ldapResponse.data.message || 'Invalid username or password'
      }

      error.value = errorMessage
      return {
        success: false,
        error: errorMessage
      }
    }

    // If LDAP validation passes, check user in database using standardized username
    const standardizedUsername = ldapResponse.data.standardized_username || credentials.username
    const userResponse = await axios.post(`${API_BASE_URL}/validate-user`, {
      username: standardizedUsername
    })

    if (userResponse.data.status === 'error') {
      const errorMessage = 'Access Denied - User not added'
      error.value = errorMessage
      return {
        success: false,
        error: errorMessage
      }
    }

    // Get user permissions using standardized username
    const permissionsResponse = await axios.get(`${API_BASE_URL}/get-user-permissions/${standardizedUsername}`)

    if (permissionsResponse.data.status === 'success') {
      userPermissions.value = permissionsResponse.data.permissions || []
    }

    // Set user data
    user.value = userResponse.data.user
    authenticated.value = true
    validUser.value = true

  // Store in sessionStorage for persistence in current tab
  sessionStorage.setItem('user', JSON.stringify(user.value))
  sessionStorage.setItem('permissions', JSON.stringify(userPermissions.value))
  sessionStorage.setItem('authenticated', 'true')

    return {
      success: true,
      user: user.value || undefined,
      permissions: userPermissions.value
    }

  } catch (err: any) {
    // Handle specific error responses from API
    let errorMessage = 'Login failed'

    if (err.response?.data) {
      const errorData = err.response.data
      const errorType = errorData.error_type

      if (errorType === 'invalid_username') {
        errorMessage = 'Invalid username'
      } else if (errorType === 'invalid_password') {
        errorMessage = 'Invalid password'
      } else if (errorData.message) {
        errorMessage = errorData.message
      }
    } else if (err.message) {
      errorMessage = err.message
    }

    error.value = errorMessage

    return {
      success: false,
      error: errorMessage
    }
  } finally {
    loading.value = false
  }
}

export async function logout(): Promise<void> {
  try {
    // Get current user info before clearing state
    const currentUser = user.value
    const username = currentUser?.loginName || 'Unknown'

    // Call logout API with username
    await axios.post(`${API_BASE_URL}/logout`, { username })
  } catch (err) {
    // Ignore logout API errors
    console.warn('Logout API call failed:', err)
  } finally {
    // Clear local state
    authenticated.value = false
    validUser.value = false
    user.value = null
    userPermissions.value = []
    error.value = null

    // Clear sessionStorage
    sessionStorage.removeItem('user')
    sessionStorage.removeItem('permissions')
    sessionStorage.removeItem('authenticated')
  }
}

export async function checkAuthStatus(): Promise<void> {
  const storedUser = sessionStorage.getItem('user')
  const storedPermissions = sessionStorage.getItem('permissions')
  const storedAuth = sessionStorage.getItem('authenticated')

  if (!storedUser || !storedPermissions || storedAuth !== 'true') {
    clearAuthState()
    return
  }

  try {
    const parsedUser = JSON.parse(storedUser)
    const parsedPermissions = JSON.parse(storedPermissions)
    user.value = parsedUser
    userPermissions.value = parsedPermissions
    authenticated.value = true
    validUser.value = true
    const response = await axios.post(`${API_BASE_URL}/validate-session`, {
      username: parsedUser.loginName
    })
    if (response.data.status !== 'success') {
      clearAuthState()
    }
  } catch (err) {
    console.warn('Session validation failed:', err)
    clearAuthState()
  }
}
// Helper function to clear auth state without API call
function clearAuthState(): void {
  authenticated.value = false
  validUser.value = false
  user.value = null
  userPermissions.value = []
  error.value = null

  // Clear sessionStorage
  sessionStorage.removeItem('user')
  sessionStorage.removeItem('permissions')
  sessionStorage.removeItem('authenticated')
}

export async function initializeAuth(): Promise<void> {
  if (initPromise) {
    return initPromise
  }
  initPromise = (async () => {
    if (authInitialized.value) {
      return
    }
    loading.value = true
    try {
      await checkAuthStatus()
    } finally {
      loading.value = false
      authInitialized.value = true
    }
  })()
  return initPromise
}
export function waitForAuthInit(): Promise<void> {
  if (authInitialized.value) {
    return Promise.resolve()
  }
  if (initPromise) {
    return initPromise
  }
  return initializeAuth()
}

// Permission Functions
export function hasPermission(permission: string): boolean {
  return userPermissions.value.includes(permission)
}

export function hasAnyPermission(permissions: string[]): boolean {
  return permissions.some(permission => hasPermission(permission))
}

export function hasAllPermissions(permissions: string[]): boolean {
  return permissions.every(permission => hasPermission(permission))
}

// User Display Functions
export function getUserDisplayName(): string {
  if (user.value) {
    return user.value.userName || user.value.loginName
  }
  return 'Unknown User'
}

export function getUserRole(): string {
  return user.value?.defaultRole || 'Unassigned'
}

// Utility Functions
export function isAuthenticated(): boolean {
  return authenticated.value && validUser.value
}

export function getAuthError(): string | null {
  return error.value
}

export function clearAuthError(): void {
  error.value = null
}

export function isLoading(): boolean {
  return loading.value
}