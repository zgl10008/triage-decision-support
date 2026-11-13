package org.checkclassification.pojo.dto;

 // IdListRequest

import lombok.Data;

import java.util.List;

@Data
public class IdListRequest {
    private List<Long> ids;
}
