import '@/styles/globals.css'
import type { AppProps } from 'next/app'
import Head from 'next/head'

export default function App({ Component, pageProps }: AppProps) {
  return (
    <>
      <Head>
        <title>AI BA Workflow Agent</title>
        <meta property="og:title" content="AI BA Workflow Agent" />
      </Head>
      <Component {...pageProps} />
    </>
  )
}
