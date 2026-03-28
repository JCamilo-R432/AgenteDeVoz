-- Redis Rate Limiting - AgenteDeVoz
-- Gap #14: Rate Limiting con Redis (Sliding Window)
-- Ejecutar via redis-cli EVAL o desde cliente Redis

-- Script: Sliding Window Rate Limiter
-- KEYS[1] = rate limit key (ej: "rl:ip:192.168.1.1")
-- ARGV[1] = window size en segundos
-- ARGV[2] = max requests en la ventana
-- ARGV[3] = timestamp actual en ms (tonos epoch)

local key = KEYS[1]
local window = tonumber(ARGV[1])       -- ej: 60 (segundos)
local limit = tonumber(ARGV[2])        -- ej: 100 (max requests)
local now = tonumber(ARGV[3])          -- timestamp actual ms

-- Limpiar entradas antiguas (fuera de la ventana)
local window_start = now - (window * 1000)
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

-- Contar requests en la ventana actual
local count = redis.call('ZCARD', key)

if count < limit then
    -- Permitir: agregar timestamp actual
    redis.call('ZADD', key, now, now)
    redis.call('EXPIRE', key, window)
    return {1, limit - count - 1, 0}  -- {allowed, remaining, retry_after}
else
    -- Denegar: calcular tiempo hasta que expire el mas antiguo
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = 0
    if #oldest > 0 then
        retry_after = math.ceil((tonumber(oldest[2]) + (window * 1000) - now) / 1000)
    end
    return {0, 0, retry_after}  -- {denied, remaining=0, retry_after_s}
end


-- ============================================================
-- Script: Token Bucket Rate Limiter
-- KEYS[1] = bucket key (ej: "tb:user:abc123")
-- ARGV[1] = rate (tokens per second)
-- ARGV[2] = burst (max tokens)
-- ARGV[3] = requested tokens
-- ARGV[4] = current timestamp (float seconds)
-- ============================================================
-- Usage example (separate script):
--[[
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local burst = tonumber(ARGV[2])
local requested = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or burst
local last_refill = tonumber(bucket[2]) or now

-- Rellenar tokens
local elapsed = now - last_refill
local new_tokens = math.min(burst, tokens + (elapsed * rate))

if new_tokens >= requested then
    redis.call('HMSET', key, 'tokens', new_tokens - requested, 'last_refill', now)
    redis.call('EXPIRE', key, math.ceil(burst / rate) + 1)
    return {1, math.floor(new_tokens - requested)}
else
    return {0, math.floor(new_tokens)}
end
--]]


-- ============================================================
-- Script: DDoS Detection - Global RPS Counter
-- KEYS[1] = global counter key
-- ARGV[1] = window (seconds)
-- ARGV[2] = rps threshold
-- ARGV[3] = timestamp ms
-- ============================================================
--[[
local key = KEYS[1]
local window = tonumber(ARGV[1])
local threshold = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

redis.call('ZADD', key, now, now .. math.random())
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - (window * 1000))
redis.call('EXPIRE', key, window + 1)

local count = redis.call('ZCARD', key)
local rps = count / window

if rps > threshold then
    return {1, rps}  -- under_attack=1
else
    return {0, rps}
end
--]]
