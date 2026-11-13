package org.checkclassification.service.impl;

 // InjuryTreatmentServiceImpl

import org.checkclassification.mapper.InjuryTreatmentMapper;
import org.checkclassification.pojo.entity.InjuryTreatment;
import org.checkclassification.service.InjuryTreatmentService;
import org.springframework.stereotype.Service;
import org.springframework.beans.factory.annotation.Autowired;
import java.util.*;

@Service
public class InjuryTreatmentServiceImpl implements InjuryTreatmentService {

    @Autowired
    private InjuryTreatmentMapper injuryTreatmentMapper;

    @Override
    public Map<String, List<String>> getTreatmentByInjuryType(String injuryType) {
        // 1. 入参校验
        if (injuryType == null || injuryType.trim().isEmpty()) {
            return Collections.emptyMap();
        }

        List<InjuryTreatment> treatmentList = injuryTreatmentMapper.selectByInjuryType(injuryType.trim());

        Map<String, List<String>> resultMap = new HashMap<>();
        for (InjuryTreatment treatment : treatmentList) {
            String type = treatment.getClassification();
            String content = treatment.getDescription(); // 具体建议

            resultMap.computeIfAbsent(type, k -> new ArrayList<>()).add(content);
        }

        return resultMap;
    }
}
