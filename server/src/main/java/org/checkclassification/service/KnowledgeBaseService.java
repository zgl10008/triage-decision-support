package org.checkclassification.service;

 // KnowledgeBaseService

import org.checkclassification.pojo.dto.KnowledgeRecordUpsertRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.io.IOException;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.stream.Collectors;

@Service
public class KnowledgeBaseService {

    @Value("${knowledge-base.csv-path}")
    private String csvPathConfig;

    @Value("${knowledge-base.txt-path}")
    private String txtPathConfig;

    @Value("${knowledge-base.charset:UTF-8}")
    private String fileCharsetConfig;

    public Map<String, Object> list(String injuryType, String categoryType, String detailKeyword) throws IOException {
        List<String> lines = readAllLines();
        CsvData csvData = parseCsv(lines);

        List<Map<String, Object>> records = csvData.records.stream()
                .filter(r -> !StringUtils.hasText(injuryType) || injuryType.equals(r.injuryType()))
                .filter(r -> !StringUtils.hasText(categoryType) || categoryType.equals(r.categoryType()))
                .filter(r -> !StringUtils.hasText(detailKeyword) || (r.detail() != null && r.detail().contains(detailKeyword)))
                .map(this::toRecordMap)
                .collect(Collectors.toList());

        Map<String, Object> data = new HashMap<>();
        data.put("records", records);
        data.put("injuryTypes", csvData.records.stream().map(KnowledgeRecord::injuryType).filter(StringUtils::hasText).distinct().toList());
        data.put("categoryTypes", csvData.records.stream().map(KnowledgeRecord::categoryType).filter(StringUtils::hasText).distinct().toList());
        return data;
    }

    public void create(KnowledgeRecordUpsertRequest request) throws IOException {
        validateRequest(request);
        List<String> lines = readAllLines();
        CsvData csvData = parseCsv(lines);

        int nextRowNo = csvData.records.stream().mapToInt(KnowledgeRecord::rowNo).max().orElse(0) + 1;
        csvData.records.add(new KnowledgeRecord(nextRowNo, request.getInjuryType(), request.getCategoryType(), request.getDetail()));
        writeCsv(csvData);
        syncTxt(csvData.records);
    }

    public void update(Integer rowNo, KnowledgeRecordUpsertRequest request) throws IOException {
        validateRequest(request);
        if (rowNo == null || rowNo <= 0) {
            throw new IllegalArgumentException("rowNo required");
        }

        List<String> lines = readAllLines();
        CsvData csvData = parseCsv(lines);
        boolean updated = false;
        for (int i = 0; i < csvData.records.size(); i++) {
            KnowledgeRecord item = csvData.records.get(i);
            if (item.rowNo() == rowNo) {
                csvData.records.set(i, new KnowledgeRecord(item.rowNo(), request.getInjuryType(), request.getCategoryType(), request.getDetail()));
                updated = true;
                break;
            }
        }
        if (!updated) {
            throw new IllegalArgumentException("row not found");
        }
        writeCsv(csvData);
        syncTxt(csvData.records);
    }

    public void delete(Integer rowNo) throws IOException {
        if (rowNo == null || rowNo <= 0) {
            throw new IllegalArgumentException("rowNo required");
        }
        List<String> lines = readAllLines();
        CsvData csvData = parseCsv(lines);
        boolean removed = csvData.records.removeIf(item -> item.rowNo() == rowNo);
        if (!removed) {
            throw new IllegalArgumentException("row not found");
        }
        writeCsv(csvData);
        syncTxt(csvData.records);
    }

    private List<String> readAllLines() throws IOException {
        Path csvPath = getCsvPath();
        if (!Files.exists(csvPath)) {
            throw new IllegalStateException("knowledge csv file not found: " + csvPath);
        }
        return Files.readAllLines(csvPath, getFileCharset());
    }

    private CsvData parseCsv(List<String> lines) {
        if (lines.isEmpty()) {
            return new CsvData(List.of("伤情类型", "分类类型", "具体描述"), new ArrayList<>());
        }
        List<String> header = parseCsvLine(lines.get(0));
        if (header.size() < 3) {
            header = List.of("伤情类型", "分类类型", "具体描述");
        }

        List<KnowledgeRecord> records = new ArrayList<>();
        for (int i = 1; i < lines.size(); i++) {
            List<String> row = parseCsvLine(lines.get(i));
            while (row.size() < 3) {
                row.add("");
            }
            records.add(new KnowledgeRecord(i, row.get(0), row.get(1), row.get(2)));
        }
        return new CsvData(header, records);
    }

    private void writeCsv(CsvData csvData) throws IOException {
        List<String> lines = new ArrayList<>();
        lines.add(toCsvLine(csvData.header));
        for (KnowledgeRecord item : csvData.records) {
            lines.add(toCsvLine(List.of(
                    safe(item.injuryType()),
                    safe(item.categoryType()),
                    safe(item.detail())
            )));
        }
        Files.write(getCsvPath(), lines, getFileCharset());
    }

    private void syncTxt(List<KnowledgeRecord> records) throws IOException {
        List<String> lines = records.stream()
                .map(item -> "('" + safe(item.injuryType()) + "','" + safe(item.categoryType()) + "','" + safe(item.detail()) + "')")
                .collect(Collectors.toList());
        Files.write(getTxtPath(), lines, getFileCharset());
    }

    private Map<String, Object> toRecordMap(KnowledgeRecord item) {
        Map<String, Object> map = new HashMap<>();
        map.put("rowNo", item.rowNo());
        map.put("injuryType", item.injuryType());
        map.put("categoryType", item.categoryType());
        map.put("detail", item.detail());
        return map;
    }

    private void validateRequest(KnowledgeRecordUpsertRequest request) {
        if (request == null ||
                !StringUtils.hasText(request.getInjuryType()) ||
                !StringUtils.hasText(request.getCategoryType()) ||
                !StringUtils.hasText(request.getDetail())) {
            throw new IllegalArgumentException("injuryType, categoryType and detail are required");
        }
    }

    private String safe(String value) {
        return value == null ? "" : value;
    }

    private List<String> parseCsvLine(String line) {
        List<String> result = new ArrayList<>();
        if (line == null) {
            return result;
        }
        StringBuilder sb = new StringBuilder();
        boolean inQuotes = false;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (c == '"') {
                if (inQuotes && i + 1 < line.length() && line.charAt(i + 1) == '"') {
                    sb.append('"');
                    i++;
                } else {
                    inQuotes = !inQuotes;
                }
            } else if (c == ',' && !inQuotes) {
                result.add(sb.toString());
                sb.setLength(0);
            } else {
                sb.append(c);
            }
        }
        result.add(sb.toString());
        return result;
    }

    private String toCsvLine(List<String> columns) {
        return columns.stream().map(this::escapeCsvValue).collect(Collectors.joining(","));
    }

    private String escapeCsvValue(String value) {
        String safeValue = safe(value);
        boolean needQuote = safeValue.contains(",") || safeValue.contains("\"") || safeValue.contains("\n") || safeValue.contains("\r");
        if (!needQuote) {
            return safeValue;
        }
        return "\"" + safeValue.replace("\"", "\"\"") + "\"";
    }

    private Path getCsvPath() {
        return Path.of(csvPathConfig);
    }

    private Path getTxtPath() {
        return Path.of(txtPathConfig);
    }

    private Charset getFileCharset() {
        if (!StringUtils.hasText(fileCharsetConfig)) {
            return StandardCharsets.UTF_8;
        }
        return Charset.forName(fileCharsetConfig);
    }

    private record KnowledgeRecord(int rowNo, String injuryType, String categoryType, String detail) {
    }

    private record CsvData(List<String> header, List<KnowledgeRecord> records) {
    }
}
