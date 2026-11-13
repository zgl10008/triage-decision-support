import request from '../utils/request';

const assessmentApi = {
  createAssessment: (payload) => request.post('/api/assessments', payload),
  updateAssessment: (payload) => request.put('/api/assessments', payload),
  deleteAssessment: (uid) => request.delete(`/api/assessments/${uid}`),
  getPatientList: (keyword = '') => request.get('/api/assessments/list', { params: { keyword } }),
  getPatientPage: (pageNum = 1, pageSize = 10, keyword = '') =>
    request.get('/api/assessments/page', { params: { pageNum, pageSize, keyword } }),
  getPatientDetail: (uid) => request.get(`/api/assessments/${uid}`)
};

export default assessmentApi;
