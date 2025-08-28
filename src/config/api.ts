// API Configuration
export const API_CONFIG = {
  // Base URL for API calls
  BASE_URL: '/api',
  
  // API Endpoints
  ENDPOINTS: {
    // Authentication
    LOGIN: '/validate-ldap-user',
    VALIDATE_USER: '/validate-user',
    GET_PERMISSIONS: '/get-user-permissions',
    VALIDATE_SESSION: '/validate-session',
    LOGOUT: '/logout',
    
    // User Management
    GET_USERS: '/get_user_records',
    SAVE_USER: '/save_user_record',
    UPDATE_USER: '/update_user_record',
    
    // Role Management
    GET_ROLES: '/get_role_records',
    SAVE_ROLE: '/save_role_record',
    UPDATE_ROLE: '/update_role_record',
    GET_ROLE_FUNCTIONS: '/get_role_function_records',
    
    // Function Management
    GET_FUNCTIONS: '/get_function_records',
    SAVE_FUNCTION: '/save_function_record',
    UPDATE_FUNCTION: '/update_function_record',
    
    // ECL Operations
    UPLOAD_FILE: '/upload',
    RUN_ECL: '/run-ecl',
    GET_ECL_STATUS: '/get-ecl-status',
    GET_ECL_RESULT: '/get-ecl-result',
    
    // Reporting
    GET_REPORTS: '/get-reports',
    DOWNLOAD_REPORT: '/download-report'
  },
  
  // Request timeout (milliseconds)
  TIMEOUT: 30000,
  
  // Retry configuration
  RETRY: {
    MAX_ATTEMPTS: 3,
    DELAY: 1000
  }
}

// Helper function to build full API URL
export function buildApiUrl(endpoint: string): string {
  return `${API_CONFIG.BASE_URL}${endpoint}`
}

// Helper function to get endpoint by key
export function getEndpoint(key: keyof typeof API_CONFIG.ENDPOINTS): string {
  return API_CONFIG.ENDPOINTS[key]
}

// Environment-specific configuration
export const ENV_CONFIG = {
  DEVELOPMENT: {
    API_BASE_URL: 'http://localhost:5010/api',
    DEBUG: true
  },
  PRODUCTION: {
    API_BASE_URL: '/api',
    DEBUG: false
  }
}

// Get current environment configuration
export function getCurrentEnvConfig() {
  const isDevelopment = import.meta.env.DEV
  return isDevelopment ? ENV_CONFIG.DEVELOPMENT : ENV_CONFIG.PRODUCTION
} 