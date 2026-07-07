from __future__ import annotations

import secrets
from datetime import datetime
from decimal import Decimal
from typing import Any

from server.integrations.activity_provider.base import (
    ActivityProvider,
    ProviderActivity,
    ProviderAuthResult,
    ProviderError,
    ProviderLap,
)

MFA_STATE_CACHE: dict[str, dict[str, Any]] = {}


class GarminActivityProvider(ActivityProvider):
    connector_version = "garminconnect-provider-v1"

    def __init__(self) -> None:
        self._client: Any | None = None

    def authenticate(self, username: str, password: str, region: str | None = None) -> ProviderAuthResult:
        try:
            from garminconnect import Garmin  # type: ignore
        except Exception as exc:
            raise ProviderError(
                "PROVIDER_UNAVAILABLE",
                "当前部署未安装 Garmin 连接器，无法执行真实 Garmin 登录。",
            ) from exc
        client = Garmin(
            username,
            password,
            is_cn=_is_cn_region(region),
            return_on_mfa=True,
        )
        try:
            token1, token2 = client.login()
        except Exception as exc:
            _raise_safe_provider_error(exc)
        if token1 == "needs_mfa" and isinstance(token2, dict):
            mfa_token = secrets.token_urlsafe(32)
            MFA_STATE_CACHE[mfa_token] = {
                "client_state": token2,
                "region": region,
                "account_identifier": username,
            }
            return ProviderAuthResult(
                status="mfa_required",
                account_identifier=username,
                masked_account_identifier=_mask_account(username),
                mfa_token=mfa_token,
                safe_message="Garmin 账号需要 MFA 验证。",
            )
        self._client = client
        tokenstore = client.garth.dumps()
        return ProviderAuthResult(
            status="connected",
            token_payload={"tokenstore": tokenstore, "region": region or "global"},
            account_identifier=username,
            masked_account_identifier=_mask_account(username),
            provider_user_id=None,
        )

    def submit_mfa(self, mfa_token: str, mfa_code: str) -> ProviderAuthResult:
        try:
            import garth.sso
        except Exception as exc:
            raise ProviderError(
                "PROVIDER_UNAVAILABLE",
                "当前部署未安装 Garmin MFA 连接器。",
            ) from exc
        state = MFA_STATE_CACHE.pop(mfa_token, None)
        if state is None:
            raise ProviderError("AUTHENTICATION_REQUIRED", "Garmin MFA 会话已过期，请重新连接。")
        try:
            garth.sso.resume_login(state["client_state"], mfa_code)
            client = state["client_state"]["client"]
        except Exception as exc:
            _raise_safe_provider_error(exc)
        self._client = client
        return ProviderAuthResult(
            status="connected",
            token_payload={"tokenstore": client.dumps(), "region": state.get("region") or "global"},
            account_identifier=state.get("account_identifier"),
            masked_account_identifier=_mask_account(state.get("account_identifier") or ""),
            provider_user_id=None,
        )

    def restore_session(self, token_payload: dict[str, Any]) -> None:
        try:
            from garminconnect import Garmin
        except Exception as exc:
            raise ProviderError(
                "PROVIDER_UNAVAILABLE",
                "当前部署未安装 Garmin 连接器，无法恢复会话。",
            ) from exc
        tokenstore = token_payload.get("tokenstore")
        if not tokenstore:
            raise ProviderError("REAUTHENTICATION_REQUIRED", "Garmin 连接需要重新认证。")
        client = Garmin(is_cn=_is_cn_region(token_payload.get("region")))
        try:
            client.login(tokenstore=tokenstore)
        except Exception as exc:
            _raise_safe_provider_error(exc, reauth=True)
        self._client = client

    def refresh_session(self) -> dict[str, Any] | None:
        if self._client is None:
            return None
        return {"tokenstore": self._client.garth.dumps(), "region": "cn" if self._client.is_cn else "global"}

    def fetch_activities(self, start: datetime, end: datetime) -> list[ProviderActivity]:
        client = self._require_client()
        try:
            rows = client.get_activities_by_date(
                start.date().isoformat(),
                end.date().isoformat(),
                activitytype="running",
            )
        except Exception as exc:
            raise ProviderError("ACTIVITY_FETCH_FAILED", "Garmin 活动列表拉取失败。") from exc
        activities: list[ProviderActivity] = []
        for row in rows:
            try:
                activities.append(_activity_from_payload(row, client))
            except ProviderError:
                continue
        return activities

    def fetch_activity_summary(self, external_activity_id: str) -> ProviderActivity:
        client = self._require_client()
        try:
            payload = client.get_activity(external_activity_id)
        except Exception as exc:
            raise ProviderError("ACTIVITY_FETCH_FAILED", "Garmin 活动详情拉取失败。") from exc
        return _activity_from_payload(payload, client)

    def fetch_activity_splits(self, external_activity_id: str) -> list[ProviderLap]:
        client = self._require_client()
        try:
            payload = client.get_activity_splits(external_activity_id)
        except Exception:
            return []
        return _laps_from_payload(payload)

    def fetch_activity_typed_splits(self, external_activity_id: str) -> list[ProviderLap]:
        client = self._require_client()
        try:
            payload = client.get_activity_typed_splits(external_activity_id)
        except Exception:
            return []
        return _laps_from_payload(payload)

    def fetch_activity_split_summaries(self, external_activity_id: str) -> list[ProviderLap]:
        client = self._require_client()
        try:
            payload = client.get_activity_split_summaries(external_activity_id)
        except Exception:
            return []
        return _laps_from_payload(payload)

    def fetch_activity_details(self, external_activity_id: str) -> ProviderActivity:
        return self.fetch_activity_summary(external_activity_id)

    def disconnect(self) -> None:
        self._client = None

    def health_check(self) -> bool:
        return self._client is not None

    def _require_client(self):
        if self._client is None:
            raise ProviderError("REAUTHENTICATION_REQUIRED", "Garmin 连接需要重新认证。")
        return self._client


def _mask_account(account: str) -> str:
    if "@" in account:
        name, domain = account.split("@", 1)
        prefix = name[:2]
        suffix = name[-2:] if len(name) > 4 else ""
        return f"{prefix}****{suffix}@{domain}"
    return f"{account[:2]}****{account[-2:]}" if len(account) > 4 else "****"


def _is_cn_region(region: str | None) -> bool:
    return (region or "").strip().lower() in {"cn", "china", "garmin.cn", "zh-cn"}


def _raise_safe_provider_error(exc: Exception, *, reauth: bool = False) -> None:
    text = str(exc).lower()
    if reauth:
        raise ProviderError("REAUTHENTICATION_REQUIRED", "Garmin 连接需要重新认证。") from exc
    if "429" in text or "rate" in text:
        raise ProviderError("RATE_LIMITED", "Garmin 请求过于频繁，请稍后再试。") from exc
    if "mfa" in text or "two" in text:
        raise ProviderError("MFA_REQUIRED", "Garmin 账号需要 MFA 验证。") from exc
    if "401" in text or "unauthorized" in text or "authentication" in text or "login failed" in text:
        raise ProviderError("AUTHENTICATION_REQUIRED", "Garmin 认证失败，请检查账号、密码和账号区域。") from exc
    raise ProviderError("PROVIDER_UNAVAILABLE", "Garmin 服务暂时不可用，请稍后再试。") from exc


def _activity_from_payload(payload: dict[str, Any], client: Any | None = None) -> ProviderActivity:
    external_id = str(_first(payload, "activityId", "activity_id", "id") or "")
    if not external_id:
        raise ProviderError("ACTIVITY_PARSE_FAILED", "Garmin 活动缺少外部 ID。")
    start_time = _parse_datetime(
        _first(
            payload,
            "startTimeLocal",
            "startTimeGMT",
            "beginTimestamp",
            "activityStartTimeLocal",
        )
    )
    if start_time is None:
        raise ProviderError("ACTIVITY_PARSE_FAILED", "Garmin 活动缺少开始时间。")
    raw_type = _activity_type(payload)
    laps = _laps_from_payload(payload)
    if not laps and client is not None:
        try:
            laps = _laps_from_payload(client.get_activity_splits(external_id))
        except Exception:
            laps = []
    return ProviderActivity(
        external_activity_id=external_id,
        activity_name=_text(_first(payload, "activityName", "activity_name", "name")),
        activity_type=raw_type,
        activity_subtype=_text(_first(payload, "activityTypeDTO", "activityType", "activitySubTypeDTO")),
        start_time_local=start_time,
        timezone=_text(_first(payload, "timeZoneUnitDTO", "timeZoneId")) or "Asia/Shanghai",
        start_time_utc=_parse_datetime(_first(payload, "startTimeGMT", "startTimeUTC")),
        source_updated_at=_parse_datetime(_first(payload, "lastUpdatedDate", "updateDate")),
        distance_m=_decimal(_first(payload, "distance", "sumDistance")),
        duration_seconds=_seconds(_first(payload, "duration", "elapsedDuration")),
        timer_time_seconds=_seconds(_first(payload, "movingDuration", "duration")),
        moving_time_seconds=_seconds(_first(payload, "movingDuration")),
        elapsed_time_seconds=_seconds(_first(payload, "elapsedDuration")),
        average_speed_mps=_decimal(_first(payload, "averageSpeed", "avgSpeed")),
        max_speed_mps=_decimal(_first(payload, "maxSpeed")),
        average_heart_rate_bpm=_int(_first(payload, "averageHR", "avgHR", "averageHeartRate")),
        max_heart_rate_bpm=_int(_first(payload, "maxHR", "maxHeartRate")),
        average_cadence_spm=_int(_first(payload, "averageRunningCadenceInStepsPerMinute", "averageRunCadence", "avgRunCadence")),
        max_cadence_spm=_int(_first(payload, "maxRunningCadenceInStepsPerMinute", "maxRunCadence")),
        elevation_gain_m=_int(_first(payload, "elevationGain", "sumElevationGain")),
        elevation_loss_m=_int(_first(payload, "elevationLoss", "sumElevationLoss")),
        calories_kcal=_int(_first(payload, "calories", "activeKilocalories")),
        garmin_aerobic_training_effect=_decimal(_first(payload, "aerobicTrainingEffect")),
        garmin_anaerobic_training_effect=_decimal(_first(payload, "anaerobicTrainingEffect")),
        garmin_training_load=_decimal(_first(payload, "trainingLoad")),
        raw_payload=payload,
        laps=laps,
    )


def _laps_from_payload(payload: Any) -> list[ProviderLap]:
    rows = payload
    if isinstance(payload, dict):
        rows = _first(payload, "lapDTOs", "laps", "splitSummaries", "activitySplits", "typedSplits") or []
    if not isinstance(rows, list):
        return []
    laps: list[ProviderLap] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        speed = _decimal(_first(row, "averageSpeed", "avgSpeed"))
        laps.append(
            ProviderLap(
                lap_index=_int(_first(row, "lapIndex", "splitNumber", "stepNumber")) or index,
                external_lap_id=_text(_first(row, "lapId", "splitId")),
                start_time=_parse_datetime(_first(row, "startTimeGMT", "startTimeLocal")),
                distance_m=_decimal(_first(row, "distance", "totalDistance")),
                duration_seconds=_seconds(_first(row, "duration", "elapsedDuration")),
                timer_time_seconds=_seconds(_first(row, "movingDuration", "duration")),
                moving_time_seconds=_seconds(_first(row, "movingDuration")),
                average_speed_mps=speed,
                average_heart_rate_bpm=_int(_first(row, "averageHR", "avgHR", "averageHeartRate")),
                max_heart_rate_bpm=_int(_first(row, "maxHR", "maxHeartRate")),
                average_cadence_spm=_int(_first(row, "averageRunningCadenceInStepsPerMinute", "averageRunCadence")),
                elevation_gain_m=_int(_first(row, "elevationGain", "sumElevationGain")),
                lap_type=_text(_first(row, "lapType", "splitType")),
                workout_step_type=_text(_first(row, "workoutStepType", "stepType")),
                segment_role="unknown",
                classification_source="garmin_manual_lap",
                classification_confidence="medium",
            )
        )
    return laps


def _activity_type(payload: dict[str, Any]) -> str:
    raw = _first(payload, "activityType", "activityTypeDTO", "activitySubTypeDTO")
    if isinstance(raw, dict):
        text = str(_first(raw, "typeKey", "typeId", "displayName") or "")
    else:
        text = str(raw or "")
    return text or "running_unknown"


def _first(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, dict):
            nested = _first(value, "typeKey", "displayName", "unitKey", "value")
            if nested is not None:
                return nested
        if value is not None:
            return value
    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def _seconds(value: Any) -> int | None:
    return _int(value)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    text = str(value).strip()
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            return datetime.fromisoformat(candidate).replace(tzinfo=None)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None
