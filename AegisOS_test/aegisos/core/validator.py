"""Validator - Prompt Contract v1.0 Output Validation.

Design Principle:
- Validation is SEPARATE from execution
- Enforces Prompt Contract v1.0 output schema
- Fail fast on AI protocol violations
- No tolerance for malformed output

Responsibility:
- Validate JSON structure
- Enforce Contract v1.0 schema
- Check for extra fields (not allowed)
- Verify safety constraints

Version: 1.0
"""
import json
import re
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


# Contract version this validator enforces
CONTRACT_VERSION = "1.0"


class ValidationError(Exception):
    """Raised when AI output fails validation."""
    pass


class SafetyError(Exception):
    """Raised when action violates safety constraints."""
    pass


class ProtocolViolation(Exception):
    """Raised when AI violates Prompt Contract protocol."""
    pass


@dataclass(frozen=True)
class ValidationResult:
    """Result of validation."""
    is_valid: bool
    error_code: str
    error_message: str
    data: Optional[Dict[str, Any]] = None


class ContractSchemaValidator:
    """Validates AI output against Prompt Contract v1.0 schema.
    
    The Contract specifies EXACT structure:
    {
      "status": "success | failure",
      "prompt_version": "1.0",
      "artifacts": [...],
      "errors": [...],
      "metrics": {...}
    }
    
    Any deviation = PROTOCOL_VIOLATION
    """
    
    # Required top-level fields
    REQUIRED_FIELDS = {"status", "prompt_version", "artifacts", "errors", "metrics"}
    
    # Allowed values
    VALID_STATUS = {"success", "failure"}
    VALID_PROMPT_VERSION = {CONTRACT_VERSION}
    VALID_ARTIFACT_TYPES = {"file", "log", "data"}
    VALID_CONFIDENCE = {"high", "medium", "low"}
    
    @classmethod
    def validate(cls, output_text: str) -> ValidationResult:
        """Complete validation pipeline for AI output.
        
        Args:
            output_text: Raw AI output
            
        Returns:
            ValidationResult with is_valid flag and parsed data
            
        Raises:
            Nothing - always returns ValidationResult
        """
        # Step 1: Parse JSON
        parse_result = cls._parse_json(output_text)
        if not parse_result.is_valid:
            return parse_result
        
        data = parse_result.data
        
        # Step 2: Validate schema structure
        schema_result = cls._validate_schema_structure(data)
        if not schema_result.is_valid:
            return schema_result
        
        # Step 3: Validate field types and values
        type_result = cls._validate_field_types(data)
        if not type_result.is_valid:
            return type_result
        
        # Step 4: Validate no extra fields
        extra_result = cls._validate_no_extra_fields(data)
        if not extra_result.is_valid:
            return extra_result
        
        # Step 5: Validate artifacts
        artifact_result = cls._validate_artifacts(data.get("artifacts", []))
        if not artifact_result.is_valid:
            return artifact_result
        
        # Step 6: Validate errors on failure
        error_result = cls._validate_errors(data)
        if not error_result.is_valid:
            return error_result
        
        # All checks passed
        return ValidationResult(
            is_valid=True,
            error_code="",
            error_message="",
            data=data
        )
    
    @classmethod
    def _parse_json(cls, output_text: str) -> ValidationResult:
        """Parse and clean JSON from AI output."""
        if not output_text or not output_text.strip():
            return ValidationResult(
                is_valid=False,
                error_code="EMPTY_OUTPUT",
                error_message="AI returned empty output"
            )
        
        # Extract JSON from markdown if wrapped
        text = output_text.strip()
        
        # Remove markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            return ValidationResult(
                is_valid=False,
                error_code="JSON_PARSE_ERROR",
                error_message=f"Invalid JSON: {e}"
            )
        
        if not isinstance(data, dict):
            return ValidationResult(
                is_valid=False,
                error_code="NOT_OBJECT",
                error_message="Root must be a JSON object"
            )
        
        return ValidationResult(
            is_valid=True,
            error_code="",
            error_message="",
            data=data
        )
    
    @classmethod
    def _validate_schema_structure(cls, data: Dict[str, Any]) -> ValidationResult:
        """Validate required fields exist."""
        missing = cls.REQUIRED_FIELDS - set(data.keys())
        if missing:
            return ValidationResult(
                is_valid=False,
                error_code="MISSING_FIELDS",
                error_message=f"Missing required fields: {missing}"
            )
        
        # Check prompt_version matches contract
        if data.get("prompt_version") != CONTRACT_VERSION:
            return ValidationResult(
                is_valid=False,
                error_code="VERSION_MISMATCH",
                error_message=f"Expected prompt_version '{CONTRACT_VERSION}', got '{data.get('prompt_version')}'"
            )
        
        return ValidationResult(is_valid=True, error_code="", error_message="", data=data)
    
    @classmethod
    def _validate_field_types(cls, data: Dict[str, Any]) -> ValidationResult:
        """Validate field types and values."""
        # status
        if data.get("status") not in cls.VALID_STATUS:
            return ValidationResult(
                is_valid=False,
                error_code="INVALID_STATUS",
                error_message=f"status must be 'success' or 'failure', got '{data.get('status')}'"
            )
        
        # artifacts must be array
        if not isinstance(data.get("artifacts"), list):
            return ValidationResult(
                is_valid=False,
                error_code="INVALID_ARTIFACTS_TYPE",
                error_message="artifacts must be an array"
            )
        
        # errors must be array
        if not isinstance(data.get("errors"), list):
            return ValidationResult(
                is_valid=False,
                error_code="INVALID_ERRORS_TYPE",
                error_message="errors must be an array"
            )
        
        # metrics must be object
        if not isinstance(data.get("metrics"), dict):
            return ValidationResult(
                is_valid=False,
                error_code="INVALID_METRICS_TYPE",
                error_message="metrics must be an object"
            )
        
        # Check confidence if present
        confidence = data.get("metrics", {}).get("confidence")
        if confidence and confidence not in cls.VALID_CONFIDENCE:
            return ValidationResult(
                is_valid=False,
                error_code="INVALID_CONFIDENCE",
                error_message=f"metrics.confidence must be one of {cls.VALID_CONFIDENCE}"
            )
        
        return ValidationResult(is_valid=True, error_code="", error_message="", data=data)
    
    @classmethod
    def _validate_no_extra_fields(cls, data: Dict[str, Any]) -> ValidationResult:
        """Validate no extra top-level fields."""
        extra = set(data.keys()) - cls.REQUIRED_FIELDS
        if extra:
            return ValidationResult(
                is_valid=False,
                error_code="EXTRA_FIELDS",
                error_message=f"Extra fields not allowed: {extra}"
            )
        
        return ValidationResult(is_valid=True, error_code="", error_message="", data=data)
    
    @classmethod
    def _validate_artifacts(cls, artifacts: List[Any]) -> ValidationResult:
        """Validate each artifact structure."""
        REQUIRED_ARTIFACT_FIELDS = {"type", "path", "content"}
        
        for i, artifact in enumerate(artifacts):
            if not isinstance(artifact, dict):
                return ValidationResult(
                    is_valid=False,
                    error_code="INVALID_ARTIFACT",
                    error_message=f"Artifact[{i}] must be an object"
                )
            
            # Check required fields
            missing = REQUIRED_ARTIFACT_FIELDS - set(artifact.keys())
            if missing:
                return ValidationResult(
                    is_valid=False,
                    error_code="ARTIFACT_MISSING_FIELDS",
                    error_message=f"Artifact[{i}] missing fields: {missing}"
                )
            
            # Check type
            if artifact["type"] not in cls.VALID_ARTIFACT_TYPES:
                return ValidationResult(
                    is_valid=False,
                    error_code="INVALID_ARTIFACT_TYPE",
                    error_message=f"Artifact[{i}] type must be one of {cls.VALID_ARTIFACT_TYPES}"
                )
            
            # Check no extra fields
            extra = set(artifact.keys()) - REQUIRED_ARTIFACT_FIELDS
            if extra:
                return ValidationResult(
                    is_valid=False,
                    error_code="ARTIFACT_EXTRA_FIELDS",
                    error_message=f"Artifact[{i}] has extra fields: {extra}"
                )
        
        return ValidationResult(is_valid=True, error_code="", error_message="")
    
    @classmethod
    def _validate_errors(cls, data: Dict[str, Any]) -> ValidationResult:
        """Validate errors array on failure."""
        REQUIRED_ERROR_FIELDS = {"code", "message"}
        
        if data.get("status") == "failure":
            errors = data.get("errors", [])
            if not errors:
                return ValidationResult(
                    is_valid=False,
                    error_code="MISSING_ERROR_DETAILS",
                    error_message="Failure status requires non-empty 'errors' array"
                )
            
            for i, error in enumerate(errors):
                if not isinstance(error, dict):
                    return ValidationResult(
                        is_valid=False,
                        error_code="INVALID_ERROR",
                        error_message=f"Error[{i}] must be an object"
                    )
                
                missing = REQUIRED_ERROR_FIELDS - set(error.keys())
                if missing:
                    return ValidationResult(
                        is_valid=False,
                        error_code="ERROR_MISSING_FIELDS",
                        error_message=f"Error[{i}] missing fields: {missing}"
                    )
                
                # Check no extra fields
                extra = set(error.keys()) - REQUIRED_ERROR_FIELDS
                if extra:
                    return ValidationResult(
                        is_valid=False,
                        error_code="ERROR_EXTRA_FIELDS",
                        error_message=f"Error[{i}] has extra fields: {extra}"
                    )
        
        return ValidationResult(is_valid=True, error_code="", error_message="")


# Legacy OutputValidator for backward compatibility

class OutputValidator:
    """Legacy output validator - wraps ContractSchemaValidator."""
    
    # Dangerous patterns in shell commands (kept for safety)
    DANGEROUS_PATTERNS = [
        r'rm\s+-rf\s+/',
        r'rm\s+-rf\s+~',
        r':\(\)\{\s*:\|:&\s*\};:',  # Fork bomb
        r'>\s*/dev/null',
        r'curl.*\|.*sh',
        r'wget.*\|.*sh',
        r'eval\s*\$',
        r'eval\s*`',
    ]
    
    @classmethod
    def validate_json(cls, output_text: str) -> Dict[str, Any]:
        """Parse and validate JSON structure."""
        result = ContractSchemaValidator.validate(output_text)
        if not result.is_valid:
            raise ValidationError(result.error_message)
        return result.data
    
    @classmethod
    def validate_action_schema(cls, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate action schema structure."""
        result = ContractSchemaValidator.validate(json.dumps(data))
        if result.is_valid:
            return True, []
        else:
            return False, [result.error_message]
    
    @classmethod
    def validate_complete(cls, output_text: str, project_path: Optional[str] = None) -> Dict[str, Any]:
        """Complete validation pipeline."""
        result = ContractSchemaValidator.validate(output_text)
        if not result.is_valid:
            raise ValidationError(f"{result.error_code}: {result.error_message}")
        return result.data
    
    @classmethod
    def get_risk_level(cls, data: Dict[str, Any]) -> str:
        """Extract risk level from validated data."""
        # In Contract v1.0, confidence in metrics replaces risk_level
        return data.get("metrics", {}).get("confidence", "medium")
    
    @classmethod
    def requires_approval(cls, data: Dict[str, Any]) -> bool:
        """Check if actions require human approval."""
        # Failure always requires review
        if data.get("status") == "failure":
            return True
        
        # Low confidence requires review
        confidence = data.get("metrics", {}).get("confidence")
        if confidence == "low":
            return True
        
        return False


# Convenience functions

def validate_ai_output(output_text: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Validate AI output against Contract v1.0.
    
    Returns:
        (is_valid, error_message, parsed_data)
    """
    result = ContractSchemaValidator.validate(output_text)
    return result.is_valid, result.error_message, result.data


def quick_validate(output_text: str) -> Tuple[bool, str]:
    """Quick validation without full parsing."""
    result = ContractSchemaValidator.validate(output_text)
    return result.is_valid, result.error_message


def strict_validate(output_text: str) -> Dict[str, Any]:
    """Strict validation - raises on any error.
    
    Returns:
        Parsed data dict
        
    Raises:
        ProtocolViolation: On any validation failure
    """
    result = ContractSchemaValidator.validate(output_text)
    if not result.is_valid:
        raise ProtocolViolation(f"[{result.error_code}] {result.error_message}")
    return result.data
