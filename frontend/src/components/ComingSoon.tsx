import "./ComingSoon.css";

/** 즐겨찾기/설정 탭 -- 이번 패스는 핵심 루프(①②③)만 구현. */
export function ComingSoon({ label }: { label: string }) {
  return (
    <div className="coming-soon">
      <p>{label} 화면은 곧 제공됩니다.</p>
    </div>
  );
}
