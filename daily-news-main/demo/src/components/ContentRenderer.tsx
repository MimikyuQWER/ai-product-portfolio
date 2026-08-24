import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize from 'rehype-sanitize';
import remarkGfm from 'remark-gfm';

type Props = { markdown: string; assetBase?: string };

function headingId(children: unknown): string {
  return String(children).toLowerCase().trim().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '');
}

export default function ContentRenderer({ markdown, assetBase = '/' }: Props) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeRaw, rehypeSanitize]}
      components={{
        h2: ({ children, ...props }) => <h2 id={headingId(children)} {...props}>{children}</h2>,
        h3: ({ children, ...props }) => <h3 id={headingId(children)} {...props}>{children}</h3>,
        a: ({ href, children, ...props }) => (
          <a href={href} target={href?.startsWith('http') ? '_blank' : undefined} rel="noopener noreferrer" {...props}>{children}</a>
        ),
        img: ({ src, alt, ...props }) => {
          const resolvedSrc = src?.startsWith('/') ? `${assetBase}${src.slice(1)}` : src;
          return <img src={resolvedSrc} alt={alt || ''} loading="lazy" {...props} />;
        },
      }}
    >
      {markdown}
    </ReactMarkdown>
  );
}
