package org.checkclassification.mapper;

 // PatientMedicalInfoMapper

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.checkclassification.pojo.entity.PatientMedicalInfo;

@Mapper
public interface PatientMedicalInfoMapper extends BaseMapper<PatientMedicalInfo> {
    // MyBatis-Plus的BaseMapper已提供基本CRUD方法
}
