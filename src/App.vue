<template>
  <div>
    <!-- Navigation Bar -->
    <div class="navbar">
      <!-- Logo -->
      <div class="logo">
        <img alt="Group" src="/group.png" />
        <img alt="Vector" src="/vector.svg" />
      </div>
      
      <!-- Navigation Links -->
      <div class="nav-links">
        <router-link to="/">Home</router-link>
        <router-link to="/parameter">Parameter</router-link>
        <router-link to="/run-management">Run Management</router-link>
        <router-link to="/reporting">Reporting</router-link>
        <router-link to="/role-management">Role Management</router-link>
        <router-link to="/audit-trial">Audit Trial</router-link>
      </div>
    </div>

    <!-- Router View -->
    <router-view></router-view>
  </div>
</template>

<style scoped>
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
}

.logo {
  display: flex;
  align-items: center;
  margin-left: 27px;
}

.logo img:first-child {
  width: 42px;
  height: 41px;
  margin-right: 7px;
}

.logo img:last-child {
  width: 198px;
  height: 41px;
}

.nav-links {
  display: flex;
  gap: 30px;
  margin-left: 50px;
}

.nav-links a,
.nav-links router-link {
  text-decoration: none;
  color: #333;
  font-weight: 500;
  font-size: 18px;
  padding: 8px 4px;
  transition: color 0.3s;
}

.nav-links a:hover,
.nav-links router-link:hover {
  color: #ff612c;
}

.router-link-active {
  color: #ff612c !important;
  border-bottom: 2px solid #ff612c;
}
</style>
