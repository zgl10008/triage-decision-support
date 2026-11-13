package org.checkclassification.service;

 // InjuryTreatmentService

import java.util.Map;
import java.util.List;

public interface InjuryTreatmentService {
     // @param injuryType 伤情名称
    Map<String, List<String>> getTreatmentByInjuryType(String injuryType);
}
