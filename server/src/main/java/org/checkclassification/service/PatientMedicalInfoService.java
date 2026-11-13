package org.checkclassification.service;

 // PatientMedicalInfoService

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.IService;
import org.checkclassification.pojo.entity.PatientMedicalInfo;

public interface PatientMedicalInfoService extends IService<PatientMedicalInfo> {

     // @param page 分页对象
     // @return 分页结果
    IPage<PatientMedicalInfo> findPage(Page<PatientMedicalInfo> page, String keyword);
}
