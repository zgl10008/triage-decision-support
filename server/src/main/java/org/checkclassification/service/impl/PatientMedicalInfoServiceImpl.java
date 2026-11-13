package org.checkclassification.service.impl;

 // PatientMedicalInfoServiceImpl

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.checkclassification.mapper.PatientMedicalInfoMapper;
import org.checkclassification.pojo.entity.PatientMedicalInfo;
import org.checkclassification.service.PatientMedicalInfoService;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class PatientMedicalInfoServiceImpl extends
        ServiceImpl<PatientMedicalInfoMapper, PatientMedicalInfo>
        implements PatientMedicalInfoService {

    @Override
    public IPage<PatientMedicalInfo> findPage(Page<PatientMedicalInfo> page, String keyword) {
        QueryWrapper<PatientMedicalInfo> queryWrapper = new QueryWrapper<>();
        if (keyword != null && !keyword.trim().isEmpty()) {
            String normalizedKeyword = keyword.trim();
            queryWrapper.and(wrapper -> wrapper
                    .eq("uid", normalizedKeyword)

                    .or()
                    .like("name", normalizedKeyword));
        }
        queryWrapper.orderByDesc("create_time");
        return baseMapper.selectPage(page, queryWrapper);
    }

    @Override
    public List<PatientMedicalInfo> list() {
        QueryWrapper<PatientMedicalInfo> queryWrapper = new QueryWrapper<>();
        queryWrapper.orderByDesc("create_time");
        return baseMapper.selectList(queryWrapper);
    }
}
