import request from '../utils/request';

const toKnowledgePayload = (payload = {}) => ({
  injury_type: payload.injuryType ?? payload.injury_type ?? '',
  category_type: payload.categoryType ?? payload.category_type ?? '',
  detail: payload.detail ?? ''
});

const adminApi = {
  listUsers: (username = '') => request.get('/api/admin/users', { params: { username } }),
  createUser: (payload) => request.post('/api/admin/users', payload),
  updateUser: (payload) => request.put('/api/admin/users', payload),
  deleteUser: (id) => request.delete(`/api/admin/users/${id}`),
  getUserRoles: (id) => request.get(`/api/admin/users/${id}/roles`),
  bindUserRoles: (id, ids) => request.post(`/api/admin/users/${id}/roles`, { ids }),

  listRoles: (roleName = '') => request.get('/api/admin/roles', { params: { roleName } }),
  createRole: (payload) => request.post('/api/admin/roles', payload),
  updateRole: (payload) => request.put('/api/admin/roles', payload),
  deleteRole: (id) => request.delete(`/api/admin/roles/${id}`),
  getRolePermissions: (id) => request.get(`/api/admin/roles/${id}/permissions`),
  bindRolePermissions: (id, ids) => request.post(`/api/admin/roles/${id}/permissions`, { ids }),

  listPermissions: (permName = '') => request.get('/api/admin/permissions', { params: { permName } }),
  createPermission: (payload) => request.post('/api/admin/permissions', payload),
  updatePermission: (payload) => request.put('/api/admin/permissions', payload),
  deletePermission: (id) => request.delete(`/api/admin/permissions/${id}`),

  pageLogs: (pageNum = 1, pageSize = 20, username = '', path = '') =>
    request.get('/api/admin/logs', { params: { pageNum, pageSize, username, path } }),

  listKnowledge: (injuryType = '', categoryType = '', detailKeyword = '') =>
    request.get('/api/admin/knowledge', { params: { injuryType, categoryType, detailKeyword } }),
  createKnowledge: (payload) => request.post('/api/admin/knowledge', toKnowledgePayload(payload)),
  updateKnowledge: (rowNo, payload) => request.put(`/api/admin/knowledge/${rowNo}`, toKnowledgePayload(payload)),
  deleteKnowledge: (rowNo) => request.delete(`/api/admin/knowledge/${rowNo}`)
};

export default adminApi;
