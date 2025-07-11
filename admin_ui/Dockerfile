# 1단계: 빌드 환경
FROM node:18-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# 2단계: 프로덕션 환경
FROM nginx:1.25-alpine
# Nginx 기본 설정 파일 복사
COPY --from=builder /app/build /usr/share/nginx/html
# React Router 사용 시 필요한 Nginx 설정 추가 (옵션)
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]