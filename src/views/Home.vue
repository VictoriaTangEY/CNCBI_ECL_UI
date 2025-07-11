<template>
  <div style="width: 100%; min-height: 100vh; background: white; display: flex; justify-content: center; align-items: center; padding-top: 95px; position: relative;">
    <div style="position: relative; width: 1600px; height: 900px; display: flex; justify-content: center; align-items: center;">
      
      <!-- 中心橙色渐变圆 -->
      <div style="
        position: absolute;
        width: 900px;
        height: 900px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(255, 97, 44, 0.4) 0%, white 100%);
        box-shadow: 0 0 80px rgba(255, 97, 44, 0.2);
      "></div>

      <!-- Welcome + 文字区块 -->
      <div style="position: relative; z-index: 1; text-align: center;">
        <h1 style="
          font-size: 64px;
          font-weight: 700;
          color: #FF612C;
          margin-bottom: 40px;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen-Sans, Ubuntu, Cantarell, 'Helvetica Neue', sans-serif;
        ">
          Welcome Back!
        </h1>

        <!-- 左右结构 -->
        <div style="display: flex; flex-direction: row; justify-content: center; align-items: flex-start; gap: 120px; font-size: 24px;">
          <div style="text-align: left; color: #333; font-weight: 600; line-height: 2;">
            <div>› Upload Data</div>
            <div>› Run ECL</div>
            <div>› Role Management</div>
            <div>› Audit Trial</div>
            <div>› Reporting</div>
          </div>

          <!-- 右侧链接 -->
          <div style="text-align: left; font-weight: 600; line-height: 2;">
            <router-link to="/parameter" style="color: #FF612C; text-decoration: underline;">Parameter</router-link><br>
            <router-link to="/run-management" style="color: #FF612C; text-decoration: underline;">Run Management</router-link><br>
            <router-link to="/role-management" style="color: #FF612C; text-decoration: underline;">Role Management</router-link><br>
            <router-link to="/audit-trial" style="color: #FF612C; text-decoration: underline;">AuditTrial</router-link><br>
            <router-link to="/reporting" style="color: #FF612C; text-decoration: underline;">Reporting</router-link><br>
          </div>

        </div>
      </div>
    </div>

    <!-- 页面右下角的版本号 -->
    <div style="
      position: fixed;
      right: 20px;
      bottom: 10px;
      font-size: 20px;
      color: #999;
      z-index: 1000;
    ">
      Version: python 3.10
    </div>
  </div>
</template>
