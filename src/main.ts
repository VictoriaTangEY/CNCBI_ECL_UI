import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

// Create Vue app instance
const app = createApp(App)

// Use router
app.use(router)

// Global error handler
app.config.errorHandler = (err, instance, info) => {
  console.error('Vue Error:', err)
  console.error('Component:', instance)
  console.error('Info:', info)
}

// Global warn handler
app.config.warnHandler = (msg, instance, trace) => {
  console.warn('Vue Warning:', msg)
  console.warn('Component:', instance)
  console.warn('Trace:', trace)
}

// Mount the app
app.mount('#app')

// Log successful initialization
console.log('CNCBI ECL UI initialized successfully')