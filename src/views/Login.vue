<template>
  <div class="login-page">
    <!-- Top Navigation Bar (same as home page) -->
    <div class="navbar">
      <!-- Logo -->
      <div class="logo">
        <img alt="CNCBI" class="logo-image" src="/logo.png" />
      </div>
    </div>

    <!-- Login Content -->
    <div class="login-content">
      <div class="login-card">
        <h1 class="login-title">Expected Credit Loss System Login</h1>
        
        <form @submit.prevent="handleLogin" class="login-form">
          <!-- Username Field -->
          <div class="form-group">
            <label for="username" class="form-label">Username</label>
            <input
              id="username"
              v-model="credentials.username"
              type="text"
              class="form-input"
              :class="{ 'error': errors.username }"
              placeholder="Enter your username"
              required
              autocomplete="username"
              @input="clearFieldError('username')"
              @blur="validateUsername"
            />
            <div v-if="errors.username" class="error-message">
              {{ errors.username }}
            </div>
          </div>
          
          <!-- Password Field -->
          <div class="form-group">
            <label for="password" class="form-label">Password</label>
            <div class="password-wrapper">
              <input
                id="password"
                v-model="credentials.password"
                :type="showPassword ? 'text' : 'password'"
                class="form-input"
                :class="{ 'error': errors.password }"
                placeholder="Enter your password"
                required
                autocomplete="current-password"
                @input="clearFieldError('password')"
                @blur="validatePassword"
              />
              <button
                type="button"
                class="password-toggle"
                @click="togglePassword"
                :aria-label="showPassword ? 'Hide password' : 'Show password'"
              >
                <svg v-if="showPassword" class="eye-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" stroke-width="2"/>
                  <circle cx="12" cy="12" r="3" stroke-width="2"/>
                  <path d="M9 3l6 6M9 21l6-6" stroke-width="2"/>
                </svg>
                <svg v-else class="eye-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" stroke-width="2"/>
                  <circle cx="12" cy="12" r="3" stroke-width="2"/>
                </svg>
              </button>
            </div>
            <div v-if="errors.password" class="error-message">
              {{ errors.password }}
            </div>
          </div>
          
          <!-- Error Display -->
          <div v-if="authError" class="auth-error">
            <div class="error-icon">⚠</div>
            <span>{{ authError }}</span>
          </div>
          
          <!-- Submit Button -->
          <button
            type="submit"
            class="login-button"
            :disabled="loading || !isFormValid"
            :class="{ 'loading': loading }"
          >
            <span v-if="loading" class="loading-spinner"></span>
            <span v-else>Sign In</span>
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { login, loading, error as authError, clearAuthError } from '../services/authService'

const router = useRouter()

// Form data
const credentials = reactive({
  username: '',
  password: ''
})

// Form state
const showPassword = ref(false)
const errors = reactive({
  username: '',
  password: ''
})

// Computed properties
const isFormValid = computed(() => {
  return credentials.username.trim() !== '' && 
         credentials.password.trim() !== '' && 
         !errors.username && 
         !errors.password
})

// Methods
function validateUsername() {
  if (!credentials.username.trim()) {
    errors.username = 'Username is required'
  } else if (credentials.username.trim().length < 3) {
    errors.username = 'Username must be at least 3 characters'
  } else {
    errors.username = ''
  }
}

function validatePassword() {
  if (!credentials.password.trim()) {
    errors.password = 'Password is required'
  } else if (credentials.password.trim().length < 6) {
    errors.password = 'Password must be at least 6 characters'
  } else {
    errors.password = ''
  }
}

function togglePassword() {
  showPassword.value = !showPassword.value
}

async function handleLogin() {
  // Clear previous form field errors (but keep auth errors visible)
  errors.username = ''
  errors.password = ''
  
  // Validate form
  validateUsername()
  validatePassword()
  
  if (!isFormValid.value) {
    return
  }
  
  console.log('Starting login process...')
  
  try {
    const result = await login(credentials)
    
    console.log('Login result:', result)
    
    if (result.success) {
      console.log('Login successful, redirecting to home...')
      // Clear any auth errors before redirect
      clearAuthError()
      // Redirect to home page on successful login
      router.push('/')
    } else {
      console.log('Login failed with error:', result.error)
      console.log('Auth error from service:', authError.value)
      // Error is already set in the service, no need to set it again
    }
  } catch (err) {
    console.error('Login error:', err)
  }
}

// Clear errors when user starts typing
function clearFieldError(field: 'username' | 'password') {
  errors[field] = ''
  // Also clear auth error when user starts typing to give fresh start
  if (authError.value) {
    clearAuthError()
  }
}

// Lifecycle
onMounted(() => {
  // Component mounted - don't clear errors to allow them to persist
  console.log('Login component mounted')
})
</script>

<style scoped>
/* Main page layout */
.login-page {
  min-height: 100vh;
  background: white;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

/* Top Navigation Bar (same as main app) */
.navbar {
  position: fixed;
  top: 0;
  width: 100%;
  background: white;
  z-index: 1000;
  height: 95px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  display: flex;
  align-items: center;
  justify-content: flex-start;
}

.logo {
  display: flex;
  align-items: center;
  margin-left: 27px;
}

.logo-image {
  height: 48px;
  width: auto;
  max-width: 280px;
  object-fit: contain;
}

/* Login content area */
.login-content {
  padding-top: 95px; /* Account for fixed navbar */
  min-height: calc(100vh - 95px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

/* Login card - horizontal rectangle */
.login-card {
  background: white;
  border: 1px solid #e1e5e9;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  padding: 60px 80px;
  width: 100%;
  max-width: 600px;
  animation: fadeIn 0.6s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.login-title {
  font-size: 32px;
  font-weight: 700;
  color: #333;
  margin: 0 0 40px 0;
  text-align: center;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 25px;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-label {
  font-weight: 600;
  color: #333;
  margin-bottom: 10px;
  font-size: 16px;
}

.form-input {
  width: 100%;
  padding: 15px 20px;
  border: 2px solid #e1e5e9;
  border-radius: 8px;
  font-size: 16px;
  transition: all 0.3s ease;
  box-sizing: border-box;
}

.form-input:focus {
  outline: none;
  border-color: #FF612C;
  box-shadow: 0 0 0 3px rgba(255, 97, 44, 0.1);
}

.form-input.error {
  border-color: #e74c3c;
}

.form-input::placeholder {
  color: #999;
}

/* Password wrapper for toggle button */
.password-wrapper {
  position: relative;
}

.password-toggle {
  position: absolute;
  right: 15px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  cursor: pointer;
  padding: 5px;
  color: #666;
  transition: color 0.3s ease;
}

.password-toggle:hover {
  color: #FF612C;
}

.eye-icon {
  width: 22px;
  height: 22px;
}

.error-message {
  color: #e74c3c;
  font-size: 13px;
  margin-top: 8px;
  margin-left: 5px;
}

.auth-error {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
  padding: 16px 20px;
  border-radius: 8px;
  font-size: 14px;
}

.error-icon {
  font-size: 20px;
}

.login-button {
  background: linear-gradient(135deg, #FF612C 0%, #ff8a65 100%);
  color: white;
  border: none;
  padding: 18px 24px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  margin-top: 10px;
}

.login-button:hover:not(:disabled) {
  background: linear-gradient(135deg, #e55a24 0%, #ff7a50 100%);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(255, 97, 44, 0.3);
}

.login-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.login-button.loading {
  cursor: wait;
}

.loading-spinner {
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 2px solid transparent;
  border-top: 2px solid white;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* Responsive Design */
@media (max-width: 768px) {
  .login-card {
    padding: 40px 30px;
    margin: 20px;
  }
  
  .login-title {
    font-size: 28px;
  }
}

@media (max-width: 480px) {
  .navbar {
    height: 70px;
    padding: 0 15px;
  }
  
  .logo {
    margin-left: 15px;
  }
  
  .logo-image {
    height: 35px;
    max-width: 200px;
  }
  
  .login-content {
    padding-top: 70px;
  }
  
  .login-card {
    padding: 30px 20px;
    margin: 15px;
  }
  
  .login-title {
    font-size: 24px;
    margin-bottom: 30px;
  }
}
</style> 