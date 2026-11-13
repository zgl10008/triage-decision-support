package org.checkclassification.mapper;

 // InjuryTreatmentMapper

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.checkclassification.pojo.entity.InjuryTreatment;
import org.apache.ibatis.annotations.Param;
import java.util.List;

public interface InjuryTreatmentMapper extends BaseMapper<InjuryTreatment> {
    List<InjuryTreatment> selectByInjuryType(@Param("injuryType") String injuryType);
}
