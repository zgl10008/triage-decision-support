<template>
  <div class="admin-page">
    <header class="topbar">
      <h1>系统管理</h1>
      <div class="actions">
        <button class="btn" @click="goManage">返回伤员管理</button>
      </div>
    </header>

    <div class="tabs">
      <button :class="['tab', { active: tab === 'users' }]" @click="switchTab('users')">用户账户管理</button>
      <button :class="['tab', { active: tab === 'roles' }]" @click="switchTab('roles')">角色权限管理</button>
      <button :class="['tab', { active: tab === 'knowledge' }]" @click="switchTab('knowledge')">知识库管理</button>
      <button :class="['tab', { active: tab === 'logs' }]" @click="switchTab('logs')">日志管理</button>
    </div>

    <section v-if="tab === 'users'" class="panel">
      <div class="toolbar">
        <input v-model="userKeyword" placeholder="用户名查询" />
        <button class="btn" @click="loadUsers">查询</button>
        <button class="btn btn-primary" @click="openUserModal('create')">新增用户</button>
      </div>
      <table>
        <thead>
          <tr><th>ID</th><th>用户名</th><th>角色</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.id }}</td>
            <td>{{ u.username }}</td>
            <td>{{ formatRoleCodes(userRoleCodes[u.id]) }}</td>
            <td>
              <button class="btn" @click="openBindUserRoleModal(u)">分配角色</button>
              <button class="btn" @click="openUserModal('edit', u)">修改</button>
              <button class="btn btn-danger" @click="deleteUser(u)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-if="tab === 'roles'" class="panel">
      <div class="toolbar">
        <input v-model="roleKeyword" placeholder="角色名查询" />
        <button class="btn" @click="loadRoles">查询</button>
        <button class="btn btn-primary" @click="openRoleModal('create')">新增角色</button>
      </div>
      <table>
        <thead>
          <tr><th>ID</th><th>角色名</th><th>角色编码</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in roles" :key="r.id">
            <td>{{ r.id }}</td>
            <td>{{ roleNameOf(r) }}</td>
            <td>{{ roleCodeOf(r) }}</td>
            <td>
              <button class="btn" @click="openBindRolePermModal(r)">分配权限</button>
              <button class="btn" @click="openRoleModal('edit', r)">修改</button>
              <button class="btn btn-danger" @click="deleteRole(r)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>

      <h3 class="sub-title">权限列表</h3>
      <div class="toolbar">
        <input v-model="permKeyword" placeholder="权限名查询" />
        <button class="btn" @click="loadPermissions">查询</button>
        <button class="btn btn-primary" @click="openPermModal('create')">新增权限</button>
      </div>
      <table>
        <thead>
          <tr><th>ID</th><th>权限名</th><th>权限编码</th><th>Path</th><th>Method</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="p in permissions" :key="p.id">
            <td>{{ p.id }}</td>
            <td>{{ permNameOf(p) }}</td>
            <td>{{ permCodeOf(p) }}</td>
            <td>{{ p.path || '-' }}</td>
            <td>{{ p.method || '-' }}</td>
            <td>
              <button class="btn" @click="openPermModal('edit', p)">修改</button>
              <button class="btn btn-danger" @click="deletePermission(p)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-if="tab === 'knowledge'" class="panel">
      <div class="toolbar">
        <select v-model="knowledgeInjuryType">
          <option value="">全部伤情类型</option>
          <option v-for="item in knowledgeInjuryTypes" :key="item" :value="item">{{ item }}</option>
        </select>
        <select v-model="knowledgeCategoryType">
          <option value="">全部分类类型</option>
          <option v-for="item in knowledgeCategoryTypes" :key="item" :value="item">{{ item }}</option>
        </select>
        <input v-model="knowledgeDetailKeyword" placeholder="请输入伤情描述" />
        <button class="btn" @click="loadKnowledge">查询</button>
        <button class="btn btn-primary" @click="openKnowledgeModal('create')">新增记录</button>
      </div>
      <table>
        <thead>
          <tr><th>行号</th><th>伤情类型</th><th>分类类型</th><th>具体描述</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="k in knowledgeRecords" :key="k.rowNo">
            <td>{{ k.rowNo }}</td>
            <td>{{ k.injuryType }}</td>
            <td>{{ k.categoryType }}</td>
            <td>{{ k.detail }}</td>
            <td>
              <button class="btn" @click="openKnowledgeModal('edit', k)">修改</button>
              <button class="btn btn-danger" @click="deleteKnowledge(k)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-if="tab === 'logs'" class="panel">
      <div class="toolbar">
        <input v-model="logUser" placeholder="用户名" />
        <input v-model="logPath" placeholder="请求路径" />
        <button class="btn" @click="loadLogs(1)">查询</button>
      </div>
      <table>
        <thead>
          <tr><th>ID</th><th>用户</th><th>方法</th><th>路径</th><th>IP</th><th>状态</th><th>时间</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in logs" :key="item.id">
            <td>{{ item.id }}</td>
            <td>{{ item.username || '-' }}</td>
            <td>{{ item.requestMethod || item.request_method }}</td>
            <td>{{ item.requestPath || item.request_path }}</td>
            <td>{{ item.clientIp || item.client_ip }}</td>
            <td>{{ item.statusCode || item.status_code }}</td>
            <td>{{ item.createTime || item.create_time }}</td>
          </tr>
        </tbody>
      </table>
      <div class="pager">
        <button class="btn" :disabled="logPage <= 1" @click="loadLogs(logPage - 1)">上一页</button>
        <span>第 {{ logPage }} / {{ logPages }} 页</span>
        <button class="btn" :disabled="logPage >= logPages" @click="loadLogs(logPage + 1)">下一页</button>
      </div>
    </section>

    <div v-if="modal.visible" class="modal-mask" @click.self="closeModal">
      <div class="modal-card">
        <div class="modal-head">
          <h3>{{ modal.title }}</h3>
          <button class="icon-close" @click="closeModal">×</button>
        </div>

        <div class="modal-body" v-if="modal.type === 'user'">
          <div class="form-item">
            <label>用户名</label>
            <input v-model="userForm.username" placeholder="请输入用户名" />
          </div>
          <div class="form-item">
            <label>密码{{ modal.mode === 'edit' ? '（留空不改）' : '' }}</label>
            <input v-model="userForm.password" type="password" placeholder="请输入密码" />
          </div>
        </div>

        <div class="modal-body" v-else-if="modal.type === 'role'">
          <div class="form-item">
            <label>角色名</label>
            <input v-model="roleForm.roleName" placeholder="请输入角色名" />
          </div>
          <div class="form-item">
            <label>角色编码</label>
            <input v-model="roleForm.roleCode" placeholder="如 ADMIN / MEDIC" />
          </div>
        </div>

        <div class="modal-body" v-else-if="modal.type === 'perm'">
          <div class="form-item"><label>权限名</label><input v-model="permForm.permName" /></div>
          <div class="form-item"><label>权限编码</label><input v-model="permForm.permCode" /></div>
          <div class="form-item"><label>Path</label><input v-model="permForm.path" /></div>
          <div class="form-item"><label>Method</label><input v-model="permForm.method" placeholder="GET/POST/PUT/DELETE" /></div>
        </div>

        <div class="modal-body" v-else-if="modal.type === 'bindUserRole'">
          <div class="check-grid">
            <label v-for="r in roles" :key="r.id" class="check-item">
              <input type="checkbox" :value="r.id" v-model="bindRoleIds" />
              <span>{{ roleNameOf(r) }} ({{ roleCodeOf(r) }})</span>
            </label>
          </div>
        </div>

        <div class="modal-body" v-else-if="modal.type === 'bindRolePerm'">
          <div class="check-grid">
            <label v-for="p in permissions" :key="p.id" class="check-item">
              <input type="checkbox" :value="p.id" v-model="bindPermIds" />
              <span>{{ permNameOf(p) }} ({{ permCodeOf(p) }})</span>
            </label>
          </div>
        </div>

        <div class="modal-body" v-else-if="modal.type === 'knowledge'">
          <div class="form-item">
            <label>伤情类型</label>
            <input v-model.trim="knowledgeForm.injuryType" />
          </div>
          <div class="form-item">
            <label>分类类型</label>
            <input v-model.trim="knowledgeForm.categoryType" />
          </div>
          <div class="form-item">
            <label>具体描述</label>
            <textarea v-model.trim="knowledgeForm.detail" rows="4"></textarea>
          </div>
        </div>

        <div class="modal-foot">
          <button class="btn" @click="closeModal">取消</button>
          <button class="btn btn-primary" @click="submitModal">确定</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import adminApi from '../api/admin'

const props = defineProps({ navigateTo: Function })

const tab = ref('users')

const users = ref([])
const userRoleCodes = reactive({})
const userKeyword = ref('')

const roles = ref([])
const roleKeyword = ref('')
const permissions = ref([])
const permKeyword = ref('')

const logs = ref([])
const logUser = ref('')
const logPath = ref('')
const logPage = ref(1)
const logPages = ref(1)
const knowledgeRecords = ref([])
const knowledgeInjuryTypes = ref([])
const knowledgeCategoryTypes = ref([])
const knowledgeInjuryType = ref('')
const knowledgeCategoryType = ref('')
const knowledgeDetailKeyword = ref('')

const modal = reactive({
  visible: false,
  type: '',
  mode: 'create',
  title: '',
  targetId: null
})

const userForm = reactive({ id: null, username: '', password: '' })
const roleForm = reactive({ id: null, roleName: '', roleCode: '' })
const permForm = reactive({ id: null, permName: '', permCode: '', path: '', method: '' })
const knowledgeForm = reactive({ rowNo: null, injuryType: '', categoryType: '', detail: '' })
const bindRoleIds = ref([])
const bindPermIds = ref([])

const roleNameOf = (r) => r?.roleName || r?.role_name || ''
const roleCodeOf = (r) => r?.roleCode || r?.role_code || ''
const permNameOf = (p) => p?.permName || p?.perm_name || ''
const permCodeOf = (p) => p?.permCode || p?.perm_code || ''
const roleCodeZhMap = {
  ADMIN: '系统管理员',
  MEDIC: '医护人员'
}
const roleCodeToZh = (code) => roleCodeZhMap[code] || code
const formatRoleCodes = (codes) => {
  if (!Array.isArray(codes) || codes.length === 0) return '-'
  return codes.map(roleCodeToZh).join('、')
}

const goManage = () => {
  if (props.navigateTo) props.navigateTo('/manage')
  else window.location.hash = '/manage'
}

const switchTab = async (value) => {
  tab.value = value
  if (value === 'users') await loadUsers()
  if (value === 'roles') {
    await loadRoles()
    await loadPermissions()
  }
  if (value === 'knowledge') await loadKnowledge()
  if (value === 'logs') await loadLogs(1)
}

const loadUsers = async () => {
  const res = await adminApi.listUsers(userKeyword.value)
  users.value = res.data || []
  for (const u of users.value) {
    const roleRes = await adminApi.getUserRoles(u.id)
    userRoleCodes[u.id] = roleRes.data?.roleCodes || roleRes.data?.role_codes || []
  }
}

const loadRoles = async () => {
  const res = await adminApi.listRoles(roleKeyword.value)
  roles.value = res.data || []
}

const loadPermissions = async () => {
  const res = await adminApi.listPermissions(permKeyword.value)
  permissions.value = res.data || []
}

const loadLogs = async (page = 1) => {
  const res = await adminApi.pageLogs(page, 20, logUser.value, logPath.value)
  const data = res.data || {}
  logs.value = data.records || []
  logPage.value = data.current || 1
  logPages.value = data.pages || 1
}

const loadKnowledge = async () => {
  const res = await adminApi.listKnowledge(
    knowledgeInjuryType.value,
    knowledgeCategoryType.value,
    knowledgeDetailKeyword.value
  )
  const data = res.data || {}
  knowledgeRecords.value = data.records || []
  knowledgeInjuryTypes.value = data.injuryTypes || []
  knowledgeCategoryTypes.value = data.categoryTypes || []
}

const openUserModal = (mode, row = null) => {
  modal.visible = true
  modal.type = 'user'
  modal.mode = mode
  modal.title = mode === 'create' ? '新增用户' : '修改用户'
  userForm.id = row?.id || null
  userForm.username = row?.username || ''
  userForm.password = ''
}

const openRoleModal = (mode, row = null) => {
  modal.visible = true
  modal.type = 'role'
  modal.mode = mode
  modal.title = mode === 'create' ? '新增角色' : '修改角色'
  roleForm.id = row?.id || null
  roleForm.roleName = roleNameOf(row) || ''
  roleForm.roleCode = roleCodeOf(row) || ''
}

const openPermModal = (mode, row = null) => {
  modal.visible = true
  modal.type = 'perm'
  modal.mode = mode
  modal.title = mode === 'create' ? '新增权限' : '修改权限'
  permForm.id = row?.id || null
  permForm.permName = permNameOf(row) || ''
  permForm.permCode = permCodeOf(row) || ''
  permForm.path = row?.path || ''
  permForm.method = row?.method || ''
}

const openBindUserRoleModal = async (row) => {
  const allRolesRes = await adminApi.listRoles('')
  roles.value = allRolesRes.data || []
  const res = await adminApi.getUserRoles(row.id)
  bindRoleIds.value = res.data?.roleIds || res.data?.role_ids || []
  modal.visible = true
  modal.type = 'bindUserRole'
  modal.mode = 'edit'
  modal.title = `分配角色 - ${row.username}`
  modal.targetId = row.id
}

const openBindRolePermModal = async (row) => {
  const allPermRes = await adminApi.listPermissions('')
  permissions.value = allPermRes.data || []
  const res = await adminApi.getRolePermissions(row.id)
  bindPermIds.value = res.data?.permissionIds || res.data?.permission_ids || []
  modal.visible = true
  modal.type = 'bindRolePerm'
  modal.mode = 'edit'
  modal.title = `分配权限 - ${roleNameOf(row)}`
  modal.targetId = row.id
}

const openKnowledgeModal = (mode, row = null) => {
  modal.visible = true
  modal.type = 'knowledge'
  modal.mode = mode
  modal.title = mode === 'create' ? '新增知识库记录' : '修改知识库记录'
  knowledgeForm.rowNo = row?.rowNo || null
  knowledgeForm.injuryType = row?.injuryType || ''
  knowledgeForm.categoryType = row?.categoryType || ''
  knowledgeForm.detail = row?.detail || ''
}

const closeModal = () => {
  modal.visible = false
  modal.type = ''
  modal.targetId = null
}

const submitModal = async () => {
  if (modal.type === 'user') {
    let res
    if (modal.mode === 'create') {
      res = await adminApi.createUser({ username: userForm.username, password: userForm.password })
    } else {
      res = await adminApi.updateUser({ id: userForm.id, username: userForm.username, password: userForm.password })
    }
    alert(res.msg)
    await loadUsers()
  }

  if (modal.type === 'role') {
    let res
    if (modal.mode === 'create') {
      res = await adminApi.createRole({ roleName: roleForm.roleName, roleCode: roleForm.roleCode })
    } else {
      res = await adminApi.updateRole({ id: roleForm.id, roleName: roleForm.roleName, roleCode: roleForm.roleCode })
    }
    alert(res.msg)
    await loadRoles()
  }

  if (modal.type === 'perm') {
    let res
    const payload = { id: permForm.id, permName: permForm.permName, permCode: permForm.permCode, path: permForm.path, method: permForm.method }
    if (modal.mode === 'create') {
      res = await adminApi.createPermission(payload)
    } else {
      res = await adminApi.updatePermission(payload)
    }
    alert(res.msg)
    await loadPermissions()
  }

  if (modal.type === 'bindUserRole') {
    const res = await adminApi.bindUserRoles(modal.targetId, bindRoleIds.value)
    alert(res.msg)
    await loadUsers()
  }

  if (modal.type === 'bindRolePerm') {
    const res = await adminApi.bindRolePermissions(modal.targetId, bindPermIds.value)
    alert(res.msg)
  }

  if (modal.type === 'knowledge') {
    const payload = {
      injuryType: knowledgeForm.injuryType,
      categoryType: knowledgeForm.categoryType,
      detail: knowledgeForm.detail
    }
    let res
    if (modal.mode === 'create') {
      res = await adminApi.createKnowledge(payload)
    } else {
      res = await adminApi.updateKnowledge(knowledgeForm.rowNo, payload)
    }
    alert(res.msg)
    await loadKnowledge()
  }

  closeModal()
}

const deleteUser = async (row) => {
  if (!confirm(`确认删除用户 ${row.username} ?`)) return
  const res = await adminApi.deleteUser(row.id)
  alert(res.msg)
  await loadUsers()
}

const deleteRole = async (row) => {
  if (!confirm(`确认删除角色 ${roleNameOf(row)} ?`)) return
  const res = await adminApi.deleteRole(row.id)
  alert(res.msg)
  await loadRoles()
}

const deletePermission = async (row) => {
  if (!confirm(`确认删除权限 ${permNameOf(row)} ?`)) return
  const res = await adminApi.deletePermission(row.id)
  alert(res.msg)
  await loadPermissions()
}

const deleteKnowledge = async (row) => {
  if (!confirm(`确认删除知识记录第 ${row.rowNo} 行?`)) return
  const res = await adminApi.deleteKnowledge(row.rowNo)
  alert(res.msg)
  await loadKnowledge()
}

onMounted(async () => {
  await loadUsers()
  await loadRoles()
  await loadPermissions()
  await loadKnowledge()
  await loadLogs(1)
})
</script>

<style scoped>
.admin-page {
  min-height: 100vh;
  padding: 16px;
  color: #eaf7ff;
  background:
    radial-gradient(circle at 20% 0%, #18344a 0%, transparent 45%),
    radial-gradient(circle at 100% 100%, #102435 0%, transparent 40%),
    linear-gradient(145deg, #0a1620, #0f2735);
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.topbar h1 {
  margin: 0;
  font-size: 24px;
  letter-spacing: 1px;
}

.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.tab {
  border: 1px solid rgba(121, 199, 255, 0.35);
  background: rgba(9, 44, 63, 0.82);
  color: #d8f1ff;
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
}

.tab.active {
  border-color: #2ec8ff;
  color: #ffffff;
  box-shadow: 0 0 0 1px rgba(46, 200, 255, 0.25) inset;
}

.panel {
  background: rgba(13, 33, 46, 0.68);
  border: 1px solid rgba(121, 199, 255, 0.26);
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 12px;
  backdrop-filter: blur(6px);
  box-shadow: 0 8px 30px rgba(4, 14, 24, 0.45);
}

.sub-title {
  margin: 16px 0 8px;
  color: #d5edff;
}

.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.toolbar input {
  height: 32px;
  border: 1px solid rgba(121, 199, 255, 0.35);
  border-radius: 6px;
  padding: 0 10px;
  background: rgba(9, 44, 63, 0.78);
  color: #eaf7ff;
}

.toolbar select {
  height: 32px;
  border: 1px solid rgba(121, 199, 255, 0.35);
  border-radius: 6px;
  padding: 0 10px;
  background: rgba(9, 44, 63, 0.78);
  color: #eaf7ff;
}

.toolbar input::placeholder {
  color: #9fc2db;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th,
td {
  border-bottom: 1px solid rgba(144, 187, 218, 0.2);
  text-align: left;
  padding: 8px;
  color: #e5f4ff;
}

th {
  color: #bfe4ff;
  background: rgba(9, 44, 63, 0.55);
}

tbody tr:hover {
  background: rgba(26, 63, 88, 0.45);
}

.btn {
  height: 30px;
  border: 1px solid rgba(121, 199, 255, 0.38);
  border-radius: 6px;
  background: rgba(9, 44, 63, 0.82);
  color: #eaf7ff;
  padding: 0 10px;
  cursor: pointer;
}

.btn:hover {
  filter: brightness(1.08);
}

.btn-primary {
  border-color: rgba(46, 200, 255, 0.7);
  color: #dff6ff;
  background: linear-gradient(135deg, #1f8fbf, #2068aa);
}

.btn-danger {
  border-color: rgba(255, 126, 146, 0.45);
  color: #ffdce2;
  background: rgba(85, 28, 38, 0.72);
}

.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.actions {
  display: flex;
  gap: 8px;
}

.pager {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #c9e8ff;
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(5, 14, 23, 0.62);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-card {
  width: 560px;
  max-width: calc(100vw - 20px);
  max-height: calc(100vh - 30px);
  overflow: auto;
  background: rgba(13, 33, 46, 0.96);
  border-radius: 10px;
  border: 1px solid rgba(121, 199, 255, 0.38);
  color: #eaf7ff;
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid rgba(144, 187, 218, 0.24);
}

.modal-head h3 {
  font-size: 16px;
  margin: 0;
}

.icon-close {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: 1px solid rgba(121, 199, 255, 0.5);
  background: rgba(9, 44, 63, 0.85);
  color: #eaf7ff;
  cursor: pointer;
}

.modal-body {
  padding: 14px;
}

.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 14px 14px;
}

.form-item {
  margin-bottom: 10px;
}

.form-item label {
  display: block;
  margin-bottom: 6px;
  color: #b9ddf6;
  font-size: 13px;
}

.form-item input {
  width: 100%;
  height: 34px;
  border: 1px solid rgba(121, 199, 255, 0.38);
  border-radius: 6px;
  padding: 0 10px;
  background: rgba(9, 44, 63, 0.82);
  color: #eaf7ff;
}

.form-item textarea {
  width: 100%;
  border: 1px solid rgba(121, 199, 255, 0.38);
  border-radius: 6px;
  padding: 8px 10px;
  background: rgba(9, 44, 63, 0.82);
  color: #eaf7ff;
  resize: vertical;
}

.check-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.check-item {
  display: flex;
  gap: 8px;
  align-items: center;
  border: 1px solid rgba(121, 199, 255, 0.28);
  border-radius: 8px;
  padding: 8px;
  background: rgba(9, 44, 63, 0.42);
  color: #d9f0ff;
}

@media (max-width: 900px) {
  .check-grid {
    grid-template-columns: 1fr;
  }
}
</style>

